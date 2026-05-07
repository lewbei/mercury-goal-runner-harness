#!/usr/bin/env python3
"""Write per-step checkpoints from merged_plan.json and step_logs."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_run_path(run_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"absolute path is not allowed: {raw_path}")
    run_root = run_dir.resolve()
    resolved = (run_root / candidate).resolve()
    if resolved != run_root and run_root not in resolved.parents:
        raise ValueError(f"path escapes run folder: {raw_path}")
    return resolved


def file_state(run_dir: Path, raw_path: str) -> dict:
    path = resolve_run_path(run_dir, raw_path)
    rel_path = path.resolve().relative_to(run_dir.resolve()).as_posix()
    exists = path.is_file()
    return {
        "path": rel_path,
        "exists": exists,
        "sha256": sha256_file(path) if exists else "",
    }


def sorted_step_logs(step_dir: Path) -> list[Path]:
    def sort_key(path: Path):
        try:
            return int(path.stem)
        except ValueError:
            return path.stem

    return sorted(step_dir.glob("*.json"), key=sort_key)


def write_checkpoints(run_dir: Path) -> dict:
    goal = load_json(run_dir / "goal_contract.json")
    merged = load_json(run_dir / "merged_plan.json")
    steps = merged.get("steps", [])
    logs = sorted_step_logs(run_dir / "step_logs")
    checkpoint_dir = run_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    checkpoints = []
    for index, log_path in enumerate(logs, start=1):
        step_log = load_json(log_path)
        expected_step = steps[index - 1] if index <= len(steps) else {}
        expected_next = steps[index]["task_id"] if index < len(steps) else ""
        touched = []
        for raw_path in step_log.get("files_touched", []):
            if isinstance(raw_path, str):
                touched.append(file_state(run_dir, raw_path))
        expected_artifacts = []
        for artifact in expected_step.get("produces", []):
            if isinstance(artifact, dict) and isinstance(artifact.get("path"), str):
                expected_artifacts.append(file_state(run_dir, artifact["path"]))

        checkpoint = {
            "run_id": goal.get("run_id", run_dir.name),
            "generated_by": "checkpoint-writer-v1.5",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step_id": index,
            "current_task_id": expected_step.get("task_id", ""),
            "expected_next_task_id": expected_next,
            "files_touched": touched,
            "expected_artifacts": expected_artifacts,
        }
        checkpoint_path = checkpoint_dir / f"{index}.json"
        write_json(checkpoint_path, checkpoint)
        checkpoints.append({
            "step_id": index,
            "checkpoint_path": checkpoint_path.relative_to(run_dir).as_posix(),
        })

    manifest = {
        "run_id": goal.get("run_id", run_dir.name),
        "generated_by": "checkpoint-writer-v1.5",
        "checkpoint_count": len(checkpoints),
        "checkpoints": checkpoints,
    }
    write_json(run_dir / "checkpoint_manifest.json", manifest)
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write deterministic execution checkpoints.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    try:
        manifest = write_checkpoints(Path(args.run_dir))
    except Exception as exc:
        print(f"CHECKPOINT_WRITE_FAILED: {exc}")
        return 1
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
