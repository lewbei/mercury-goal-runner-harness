#!/usr/bin/env python3
"""Validate v0.3 Artifact-Linked PlanGraph files for one run.

The validator is intentionally deterministic. It checks exact artifact IDs,
run-relative paths, producer/consumer links, and whether produced artifacts
exist after the worker ran.
"""
import json
import sys
from pathlib import Path

from validate_schema import validate


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / ".agentic-pi" / "schemas"


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def resolve_run_path(run_dir: Path, raw_path: str) -> Path:
    if not raw_path:
        return run_dir / "unknown"
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"absolute artifact path is not allowed: {raw_path}")
    run_root = run_dir.resolve()
    resolved = (run_root / candidate).resolve()
    if resolved != run_root and run_root not in resolved.parents:
        raise ValueError(f"artifact path escapes run folder: {raw_path}")
    return resolved


def validate_file_schema(schema_name: str, instance_name: str, instance, errors):
    schema = load_json(SCHEMA_DIR / schema_name)
    schema_errors = validate(instance, schema)
    for item in schema_errors:
        errors.append(f"{instance_name} schema validation failed: {item}")


def unique_by(items, key, label, errors):
    seen = {}
    for item in items:
        value = item.get(key) if isinstance(item, dict) else None
        if value in seen:
            errors.append(f"duplicate {label}: {value}")
        else:
            seen[value] = item
    return seen


def derive_graph(graph, errors):
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_by_id = unique_by(nodes, "node_id", "graph node_id", errors)
    task_ids = []
    task_positions = {}
    artifact_nodes = {}

    for idx, node in enumerate(nodes):
        node_id = node.get("node_id")
        node_type = node.get("type")
        if node_type == "task":
            task_id = node.get("task_id")
            if task_id != node_id:
                errors.append(f"task node {node_id} must have matching task_id")
            task_ids.append(node_id)
            task_positions[node_id] = len(task_positions)
        elif node_type == "artifact":
            artifact_id = node.get("artifact_id")
            if artifact_id != node_id:
                errors.append(f"artifact node {node_id} must have matching artifact_id")
            if not node.get("path"):
                errors.append(f"artifact node {node_id} missing path")
            artifact_nodes[node_id] = node

    producers = {artifact_id: [] for artifact_id in artifact_nodes}
    required_by = {artifact_id: [] for artifact_id in artifact_nodes}
    task_requires = {task_id: [] for task_id in task_ids}
    task_produces = {task_id: [] for task_id in task_ids}
    dependencies = set()

    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        edge_type = edge.get("type")

        if source not in node_by_id:
            if edge_type == "requires":
                errors.append(f"required artifact has no producer: {source}")
            errors.append(f"edge source missing from graph nodes: {source}")
            continue
        if target not in node_by_id:
            errors.append(f"edge target missing from graph nodes: {target}")
            continue

        source_node = node_by_id[source]
        target_node = node_by_id[target]

        if edge_type == "produces":
            if source_node.get("type") != "task" or target_node.get("type") != "artifact":
                errors.append(f"produces edge must be task -> artifact: {source} -> {target}")
                continue
            producers.setdefault(target, []).append(source)
            task_produces.setdefault(source, []).append(target)
            dependencies.add((source, target, "produces"))

        elif edge_type == "requires":
            if source_node.get("type") != "artifact" or target_node.get("type") != "task":
                errors.append(f"requires edge must be artifact -> task: {source} -> {target}")
                continue
            required_by.setdefault(source, []).append(target)
            task_requires.setdefault(target, []).append(source)
            dependencies.add((source, target, "requires"))

    for artifact_id in artifact_nodes:
        artifact_producers = producers.get(artifact_id, [])
        if len(artifact_producers) == 0:
            errors.append(f"artifact has no producer: {artifact_id}")
        elif len(artifact_producers) > 1:
            errors.append(f"artifact has multiple producers: {artifact_id}")

    for task_id, required_artifacts in task_requires.items():
        for artifact_id in required_artifacts:
            artifact_producers = producers.get(artifact_id, [])
            if not artifact_producers:
                errors.append(f"task {task_id} requires unproduced artifact: {artifact_id}")
                continue
            producer = artifact_producers[0]
            if task_positions.get(producer, -1) >= task_positions.get(task_id, -1):
                errors.append(
                    f"task {task_id} starts before required artifact {artifact_id} "
                    f"is produced by {producer}"
                )

    return {
        "node_by_id": node_by_id,
        "artifact_nodes": artifact_nodes,
        "task_ids": task_ids,
        "producers": producers,
        "required_by": required_by,
        "task_requires": task_requires,
        "task_produces": task_produces,
        "dependencies": dependencies,
    }


def validate_artifact_paths(run_dir: Path, derived, errors):
    for artifact_id, node in derived["artifact_nodes"].items():
        raw_path = node.get("path")
        try:
            path = resolve_run_path(run_dir, raw_path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not path.is_file():
            errors.append(f"produced artifact missing at exact path: {artifact_id} -> {raw_path}")


def validate_registry(registry, derived, errors):
    registry_by_id = unique_by(registry, "artifact_id", "artifact_registry artifact_id", errors)
    graph_artifact_ids = set(derived["artifact_nodes"])
    registry_ids = set(registry_by_id)

    if registry_ids != graph_artifact_ids:
        missing = sorted(graph_artifact_ids - registry_ids)
        extra = sorted(registry_ids - graph_artifact_ids)
        if missing:
            errors.append(f"artifact_registry missing artifact IDs: {missing}")
        if extra:
            errors.append(f"artifact_registry has unknown artifact IDs: {extra}")

    for artifact_id in sorted(graph_artifact_ids & registry_ids):
        entry = registry_by_id[artifact_id]
        node = derived["artifact_nodes"][artifact_id]
        producer_values = derived["producers"].get(artifact_id, [])
        producer = producer_values[0] if producer_values else None
        consumers = sorted(derived["required_by"].get(artifact_id, []))

        if entry.get("path") != node.get("path"):
            errors.append(f"artifact_registry path mismatch for {artifact_id}")
        if entry.get("producer_task") != producer:
            errors.append(f"artifact_registry producer mismatch for {artifact_id}")
        if sorted(entry.get("required_by", [])) != consumers:
            errors.append(f"artifact_registry required_by mismatch for {artifact_id}")
        if entry.get("validation", {}).get("exists") is not True:
            errors.append(f"artifact_registry validation.exists must be true for {artifact_id}")


def validate_task_graph(task_graph, derived, errors):
    tasks = task_graph.get("tasks", [])
    task_by_id = unique_by(tasks, "task_id", "task_graph task_id", errors)
    graph_task_ids = set(derived["task_ids"])
    task_graph_ids = set(task_by_id)

    if task_graph_ids != graph_task_ids:
        missing = sorted(graph_task_ids - task_graph_ids)
        extra = sorted(task_graph_ids - graph_task_ids)
        if missing:
            errors.append(f"task_graph missing task IDs: {missing}")
        if extra:
            errors.append(f"task_graph has unknown task IDs: {extra}")

    for task_id in sorted(graph_task_ids & task_graph_ids):
        task = task_by_id[task_id]
        expected_requires = sorted(derived["task_requires"].get(task_id, []))
        expected_produces = sorted(derived["task_produces"].get(task_id, []))
        if sorted(task.get("requires", [])) != expected_requires:
            errors.append(f"task_graph requires mismatch for {task_id}")
        if sorted(task.get("produces", [])) != expected_produces:
            errors.append(f"task_graph produces mismatch for {task_id}")

    dependency_set = {
        (item.get("from"), item.get("to"), item.get("type"))
        for item in task_graph.get("dependencies", [])
    }
    if dependency_set != derived["dependencies"]:
        errors.append("task_graph dependencies do not match plan_graph edges")


def validate_run(run_dir: Path):
    errors = []
    graph_path = run_dir / "plan_graph.json"
    registry_path = run_dir / "artifact_registry.json"
    task_graph_path = run_dir / "task_graph.json"

    for required_path in [graph_path, registry_path, task_graph_path]:
        if not required_path.is_file():
            errors.append(f"graph file missing: {required_path.name}")
    if errors:
        return errors

    try:
        graph = load_json(graph_path)
        registry = load_json(registry_path)
        task_graph = load_json(task_graph_path)
    except Exception as exc:
        return [f"graph JSON parse failed: {exc}"]

    validate_file_schema("plan_graph.schema.json", "plan_graph.json", graph, errors)
    validate_file_schema("artifact.schema.json", "artifact_registry.json", registry, errors)
    validate_file_schema("task_graph.schema.json", "task_graph.json", task_graph, errors)

    derived = derive_graph(graph, errors)
    validate_artifact_paths(run_dir, derived, errors)
    validate_registry(registry, derived, errors)
    validate_task_graph(task_graph, derived, errors)

    return errors


def main():
    if len(sys.argv) != 2:
        print("Usage: python validate_plan_graph.py <run_dir>")
        sys.exit(2)

    run_dir = Path(sys.argv[1])
    errors = validate_run(run_dir)
    if errors:
        print("PLAN_GRAPH_INVALID")
        for error in errors:
            print(f"- {error}")
        sys.exit(1)

    print("PLAN_GRAPH_VALID")


if __name__ == "__main__":
    main()
