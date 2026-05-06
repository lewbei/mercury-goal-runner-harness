#!/usr/bin/env python3
"""Build artifact_registry.json from plan_graph.json."""
import argparse
import json
from pathlib import Path


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def resolve_run_path(run_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"absolute artifact path is not allowed: {raw_path}")
    run_root = run_dir.resolve()
    resolved = (run_root / candidate).resolve()
    if resolved != run_root and run_root not in resolved.parents:
        raise ValueError(f"artifact path escapes run folder: {raw_path}")
    return resolved


def infer_type(path_str: str) -> str:
    suffix = Path(path_str).suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".csv":
        return "csv"
    if suffix == ".py":
        return "py"
    if suffix in {".md", ".txt"}:
        return "txt"
    if suffix == ".log":
        return "log"
    return "unknown"


def is_valid_json(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        load_json(path)
    except Exception:
        return False
    return True


def build_registry(run_dir: Path, graph: dict):
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    producers = {}
    required_by = {}
    for edge in edges:
        if edge.get("type") == "produces":
            producers[edge.get("target")] = edge.get("source")
        elif edge.get("type") == "requires":
            required_by.setdefault(edge.get("source"), []).append(edge.get("target"))

    artifacts = []
    for node in nodes:
        if node.get("type") != "artifact":
            continue
        artifact_id = node.get("artifact_id")
        path = node.get("path")
        artifact_type = infer_type(path)
        resolved_path = resolve_run_path(run_dir, path)
        artifacts.append({
            "artifact_id": artifact_id,
            "producer_task": producers.get(artifact_id),
            "path": path,
            "type": artifact_type,
            "required_by": sorted(required_by.get(artifact_id, [])),
            "validation": {
                "exists": resolved_path.is_file(),
                "json_valid": is_valid_json(resolved_path) if artifact_type == "json" else False,
                "required_fields": [],
            },
        })
    return artifacts


def main():
    parser = argparse.ArgumentParser(description="Build artifact_registry.json for a run")
    parser.add_argument("run_id")
    args = parser.parse_args()

    run_dir = Path(".agentic-runs") / args.run_id
    graph_path = run_dir / "plan_graph.json"
    if not graph_path.is_file():
        raise FileNotFoundError(f"plan_graph.json missing at {graph_path}")

    registry = build_registry(run_dir, load_json(graph_path))
    out_path = run_dir / "artifact_registry.json"
    write_json(out_path, registry)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
