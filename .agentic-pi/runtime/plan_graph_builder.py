#!/usr/bin/env python3
"""Build plan_graph.json from merged_plan.json.

v0.3 keeps this deliberately narrow: task steps produce named artifacts, and
later tasks may require exact artifact IDs.
"""
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


def normalize_rel_path(run_dir: Path, raw_path: str) -> str:
    return resolve_run_path(run_dir, raw_path).relative_to(run_dir.resolve()).as_posix()


def default_artifact_id(task_id: str, path: str) -> str:
    token = path.replace("\\", "/").replace("/", ".").replace(" ", "_")
    return f"A.{task_id}.{token}".upper()


def normalize_produces(run_dir: Path, task_id: str, step: dict):
    produced = step.get("produces")
    if produced is None:
        raw_path = step.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            return []
        path = normalize_rel_path(run_dir, raw_path)
        return [{"artifact_id": default_artifact_id(task_id, path), "path": path}]

    if not isinstance(produced, list):
        raise ValueError(f"{task_id} produces must be a list")

    normalized = []
    for idx, artifact in enumerate(produced, start=1):
        if not isinstance(artifact, dict):
            raise ValueError(f"{task_id} produces[{idx}] must be an object")
        artifact_id = artifact.get("artifact_id")
        raw_path = artifact.get("path")
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            raise ValueError(f"{task_id} produces[{idx}] missing artifact_id")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"{task_id} produces[{idx}] missing path")
        normalized.append({
            "artifact_id": artifact_id,
            "path": normalize_rel_path(run_dir, raw_path),
        })
    return normalized


def normalize_requires(step: dict, task_id: str):
    requires = step.get("requires", [])
    if not isinstance(requires, list):
        raise ValueError(f"{task_id} requires must be a list")
    normalized = []
    for idx, artifact_id in enumerate(requires, start=1):
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            raise ValueError(f"{task_id} requires[{idx}] must be a non-empty artifact ID")
        normalized.append(artifact_id)
    return normalized


def build_plan_graph(run_dir: Path, merged_plan: dict):
    steps = merged_plan.get("steps", [])
    if not isinstance(steps, list) or not steps:
        raise ValueError("merged_plan.json must contain at least one step")

    nodes = []
    edges = []
    seen_nodes = set()
    seen_artifacts = {}

    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise ValueError(f"steps[{idx}] must be an object")
        task_id = step.get("task_id") or f"T{idx}"
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError(f"steps[{idx}] has invalid task_id")
        if task_id in seen_nodes:
            raise ValueError(f"duplicate task_id: {task_id}")
        seen_nodes.add(task_id)

        requires = normalize_requires(step, task_id)
        produces = normalize_produces(run_dir, task_id, step)

        nodes.append({
            "node_id": task_id,
            "type": "task",
            "task_id": task_id,
            "description": step.get("description", step.get("action", "")),
        })

        for artifact in produces:
            artifact_id = artifact["artifact_id"]
            if artifact_id in seen_artifacts and seen_artifacts[artifact_id] != artifact["path"]:
                raise ValueError(f"artifact_id {artifact_id} maps to multiple paths")
            if artifact_id not in seen_artifacts:
                seen_artifacts[artifact_id] = artifact["path"]
                nodes.append({
                    "node_id": artifact_id,
                    "type": "artifact",
                    "artifact_id": artifact_id,
                    "path": artifact["path"],
                })
            edges.append({
                "source": task_id,
                "target": artifact_id,
                "type": "produces",
            })

        for artifact_id in requires:
            edges.append({
                "source": artifact_id,
                "target": task_id,
                "type": "requires",
            })

    return {"nodes": nodes, "edges": edges}


def main():
    parser = argparse.ArgumentParser(description="Build plan_graph.json for a run")
    parser.add_argument("run_id")
    args = parser.parse_args()

    run_dir = Path(".agentic-runs") / args.run_id
    merged_path = run_dir / "merged_plan.json"
    if not merged_path.is_file():
        raise FileNotFoundError(f"merged_plan.json missing at {merged_path}")

    graph = build_plan_graph(run_dir, load_json(merged_path))
    out_path = run_dir / "plan_graph.json"
    write_json(out_path, graph)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
