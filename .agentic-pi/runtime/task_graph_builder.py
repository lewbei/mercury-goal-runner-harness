#!/usr/bin/env python3
"""Build task_graph.json from plan_graph.json and artifact_registry.json."""
import argparse
import json
from pathlib import Path


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def build_task_graph(graph: dict):
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    tasks = []
    dependencies = []
    for node in nodes:
        if node.get("type") != "task":
            continue
        task_id = node.get("task_id")
        requires = sorted(
            edge["source"]
            for edge in edges
            if edge.get("type") == "requires" and edge.get("target") == task_id
        )
        produces = sorted(
            edge["target"]
            for edge in edges
            if edge.get("type") == "produces" and edge.get("source") == task_id
        )
        tasks.append({
            "task_id": task_id,
            "title": node.get("description", task_id),
            "requires": requires,
            "produces": produces,
            "pass_condition": [],
        })
        for artifact_id in requires:
            dependencies.append({
                "from": artifact_id,
                "to": task_id,
                "type": "requires",
            })
        for artifact_id in produces:
            dependencies.append({
                "from": task_id,
                "to": artifact_id,
                "type": "produces",
            })

    return {"tasks": tasks, "dependencies": dependencies}


def main():
    parser = argparse.ArgumentParser(description="Build task_graph.json for a run")
    parser.add_argument("run_id")
    parser.add_argument("--skill-context", default=None, help="Path to skill_context.json (QRSPI skills)")
    args = parser.parse_args()

    run_dir = Path(".agentic-runs") / args.run_id
    graph_path = run_dir / "plan_graph.json"
    registry_path = run_dir / "artifact_registry.json"
    if not graph_path.is_file():
        raise FileNotFoundError(f"plan_graph.json missing at {graph_path}")
    if not registry_path.is_file():
        raise FileNotFoundError(f"artifact_registry.json missing at {registry_path}")

    task_graph = build_task_graph(load_json(graph_path))
    out_path = run_dir / "task_graph.json"
    write_json(out_path, task_graph)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
