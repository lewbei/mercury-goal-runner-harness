#!/usr/bin/env python3
"""Parallel execution using DAG from plan_graph.json.

Reads the dependency graph from plan_graph.json and identifies
independent steps that can be executed in parallel. This enables
faster execution for complex tasks with multiple independent steps.

The parallel executor:
1. Reads dependency graph from plan_graph.json
2. Identifies independent steps (no dependencies)
3. Groups steps by dependency level
4. Provides execution order for parallel execution

It does NOT certify DONE. It does NOT write final_status.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = ROOT / ".agentic-runs"
STATUS_ARTIFACTS = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}


class ParallelExecutorError(RuntimeError):
    """Raised when parallel executor cannot continue safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any = None) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        if default is not None:
            return default
        raise


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def resolve_run_dir(raw: str | None, run_id: str | None) -> Path:
    if raw:
        p = Path(raw)
        if p.is_dir():
            return p.resolve()
    if run_id:
        p = RUNS_ROOT / run_id
        if p.is_dir():
            return p.resolve()
    raise ParallelExecutorError("Provide --run-dir or --run-id with an existing run folder.")


def load_plan_graph(run_dir: Path) -> dict:
    """Load plan graph from plan_graph.json."""
    graph_path = run_dir / "plan_graph.json"
    if not graph_path.exists():
        return {"nodes": [], "edges": []}
    return load_json(graph_path, {"nodes": [], "edges": []})


def build_dependency_graph(graph: dict) -> tuple[dict, dict]:
    """Build dependency graph from plan_graph.json."""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    
    # Build adjacency lists
    # dependencies[node] = set of nodes that must complete before node
    # dependents[node] = set of nodes that depend on node
    dependencies = defaultdict(set)
    dependents = defaultdict(set)
    
    # Initialize all nodes
    for node in nodes:
        node_id = node["node_id"]
        dependencies[node_id] = set()
        dependents[node_id] = set()
    
    # Build edges
    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        # target depends on source
        dependencies[target].add(source)
        dependents[source].add(target)
    
    return dependencies, dependents


def topological_sort(dependencies: dict, dependents: dict) -> list[list[str]]:
    """Perform topological sort to find execution levels.
    
    Returns list of levels, where each level contains nodes
    that can be executed in parallel (no dependencies between them).
    """
    # Calculate in-degree for each node
    in_degree = {node: len(deps) for node, deps in dependencies.items()}
    
    # Find nodes with no dependencies (level 0)
    queue = deque([node for node, degree in in_degree.items() if degree == 0])
    
    levels = []
    while queue:
        # Current level - all nodes in queue can be executed in parallel
        current_level = list(queue)
        levels.append(current_level)
        
        # Process current level
        next_queue = deque()
        for node in current_level:
            # For each dependent of this node
            for dependent in dependents[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    next_queue.append(dependent)
        
        queue = next_queue
    
    return levels


def identify_task_nodes(graph: dict) -> list[dict]:
    """Identify task nodes in the graph."""
    nodes = graph.get("nodes", [])
    return [n for n in nodes if n.get("type") == "task"]


def analyze_parallelism(run_dir: Path) -> dict:
    """Analyze parallelism potential in the plan graph."""
    # Load plan graph
    graph = load_plan_graph(run_dir)
    
    # Build dependency graph
    dependencies, dependents = build_dependency_graph(graph)
    
    # Perform topological sort
    levels = topological_sort(dependencies, dependents)
    
    # Identify task nodes
    task_nodes = identify_task_nodes(graph)
    task_ids = {n["node_id"] for n in task_nodes}
    
    # Filter levels to only include task nodes
    task_levels = []
    for level in levels:
        task_level = [node for node in level if node in task_ids]
        if task_level:
            task_levels.append(task_level)
    
    # Calculate statistics
    total_tasks = len(task_ids)
    max_parallel = max(len(level) for level in task_levels) if task_levels else 0
    num_levels = len(task_levels)
    
    # Calculate parallelism score (0-1)
    # 1 = fully parallel (all tasks at level 0)
    # 0 = fully sequential (one task per level)
    if total_tasks <= 1:
        parallelism_score = 1.0
    else:
        parallelism_score = max_parallel / total_tasks
    
    return {
        "timestamp": utc_now(),
        "total_tasks": total_tasks,
        "num_levels": num_levels,
        "max_parallel": max_parallel,
        "parallelism_score": round(parallelism_score, 2),
        "levels": task_levels,
        "dependencies": {k: list(v) for k, v in dependencies.items()},
        "dependents": {k: list(v) for k, v in dependents.items()},
    }


def generate_execution_plan(analysis: dict) -> dict:
    """Generate execution plan from parallelism analysis."""
    levels = analysis["levels"]
    
    execution_plan = []
    for level_idx, level in enumerate(levels):
        execution_plan.append({
            "level": level_idx,
            "tasks": level,
            "can_parallel": len(level) > 1,
            "task_count": len(level),
        })
    
    return {
        "timestamp": utc_now(),
        "total_levels": len(execution_plan),
        "total_tasks": analysis["total_tasks"],
        "max_parallel": analysis["max_parallel"],
        "parallelism_score": analysis["parallelism_score"],
        "execution_plan": execution_plan,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Parallel execution using DAG from plan_graph.json.")
    parser.add_argument("--run-dir", help="Path to the run directory")
    parser.add_argument("--run-id", help="Run identifier (resolved under .agentic-runs/)")
    parser.add_argument("--output", help="Output path for execution plan JSON")
    parser.add_argument("--analyze", action="store_true", help="Analyze parallelism potential")
    args = parser.parse_args(argv)

    try:
        run_dir = resolve_run_dir(args.run_dir, args.run_id)
    except ParallelExecutorError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Analyze parallelism
    analysis = analyze_parallelism(run_dir)
    
    # Generate execution plan
    execution_plan = generate_execution_plan(analysis)
    
    # Write execution plan
    output_path = Path(args.output) if args.output else run_dir / "execution_plan.json"
    write_json(output_path, execution_plan)
    
    # Print summary
    print(f"Parallelism analysis:")
    print(f"  Total tasks: {analysis['total_tasks']}")
    print(f"  Execution levels: {analysis['num_levels']}")
    print(f"  Max parallel: {analysis['max_parallel']}")
    print(f"  Parallelism score: {analysis['parallelism_score']}")
    
    if analysis["levels"]:
        print(f"\nExecution plan:")
        for level in execution_plan["execution_plan"]:
            parallel_str = " (parallel)" if level["can_parallel"] else ""
            print(f"  Level {level['level']}: {level['task_count']} tasks{parallel_str}")
            for task in level["tasks"]:
                print(f"    - {task}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
