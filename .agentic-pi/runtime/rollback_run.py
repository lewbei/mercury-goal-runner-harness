import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


PROTECTED = {"final_status.md", "certification.json", "policy_decision.json"}
MANIFEST_REQUIRED = {
    "run_id",
    "target_path",
    "backup_path",
    "original_hash",
    "backup_hash",
    "creator",
    "timestamp",
    "phase",
    "reason",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_run_file(run_dir: Path, rel_path: str):
    target = Path(rel_path)
    if target.is_absolute():
        raise ValueError("absolute rollback path rejected")
    root = run_dir.resolve()
    resolved = (root / target).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("rollback path escapes run folder")
    normalized = target.as_posix()
    if normalized in PROTECTED or normalized.startswith("verifier_artifacts/"):
        raise ValueError("protected rollback target rejected")
    return resolved


def manifest_path_for(run_dir: Path, rel_path: str):
    return run_dir / "backups" / f"{rel_path}.backup_manifest.json"


def rollback(run_dir: Path, rel_path: str, apply: bool = False):
    violations = []
    applied = False
    mode = "apply" if apply else "dry-run"
    try:
        target = resolve_run_file(run_dir, rel_path)
    except ValueError as exc:
        violations.append(str(exc))
        target = run_dir / rel_path

    backup = run_dir / "backups" / rel_path
    manifest_path = manifest_path_for(run_dir, rel_path)
    if not backup.is_file():
        violations.append(f"backup missing: backups/{rel_path}")
    if not manifest_path.is_file():
        violations.append(f"backup manifest missing: backups/{rel_path}.backup_manifest.json")

    if not violations:
        manifest = load_json(manifest_path)
        missing = sorted(MANIFEST_REQUIRED - set(manifest))
        if missing:
            violations.append(f"backup manifest missing required fields: {', '.join(missing)}")
        if manifest.get("target_path") != rel_path:
            violations.append("backup manifest target_path mismatch")
        if manifest.get("backup_path") != f"backups/{rel_path}":
            violations.append("backup manifest backup_path mismatch")
        if manifest.get("backup_hash") != sha256_file(backup):
            violations.append("backup hash mismatch")

    if not violations and apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(backup, target)
        applied = True

    report = {
        "run_id": run_dir.name,
        "target": rel_path,
        "mode": mode,
        "applied": applied,
        "valid": not violations,
        "violations": violations,
    }
    write_json(run_dir / "rollback_report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Dry-run or apply rollback inside a run folder.")
    parser.add_argument("run_dir")
    parser.add_argument("--file", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    report = rollback(Path(args.run_dir), args.file, args.apply)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
