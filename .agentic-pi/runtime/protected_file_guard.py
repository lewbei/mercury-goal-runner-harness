#!/usr/bin/env python3
"""Protected-file snapshots for runtime enforcement.

The guard is deliberately mechanical. It does not certify DONE. It only records
whether certifier-owned files changed and whether those changes were authorized
by an allowed certifier invocation.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


PROTECTED_RELATIVE_PATHS = [
    "final_status.md",
    "certification.json",
    "policy_decision.json",
    "verifier_artifacts",
    "verifier_smell_reports",
    "verifier_strength_reports",
]

STATUS_FILES = ["final_status.md", "certification.json", "policy_decision.json"]
STATUS_RE = re.compile(r"\b(DONE_PASS|DONE_FAIL|NOT_DONE|PROVISIONAL_DONE|CERTIFIED_DONE)\b")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_run_relative(run_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"absolute protected path is not allowed: {raw_path}")
    run_root = run_dir.resolve()
    resolved = (run_root / candidate).resolve()
    if resolved != run_root and run_root not in resolved.parents:
        raise ValueError(f"protected path escapes run folder: {raw_path}")
    return resolved


def iter_protected_files(run_dir: Path):
    for raw_path in PROTECTED_RELATIVE_PATHS:
        path = ensure_run_relative(run_dir, raw_path)
        if path.is_file():
            yield path
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file():
                    yield child


def snapshot_protected_files(run_dir: Path) -> dict:
    run_dir = run_dir.resolve()
    files = {}
    for path in iter_protected_files(run_dir):
        rel_path = path.resolve().relative_to(run_dir).as_posix()
        files[rel_path] = {
            "sha256": sha256_file(path),
            "size": path.stat().st_size,
        }
    return {
        "snapshot_id": "protected_file_snapshot",
        "generated_at": utc_now(),
        "run_id": run_dir.name,
        "protected_paths": list(PROTECTED_RELATIVE_PATHS),
        "file_count": len(files),
        "files": files,
    }


def diff_snapshots(before: dict, after: dict) -> dict:
    before_files = before.get("files", {})
    after_files = after.get("files", {})
    before_paths = set(before_files)
    after_paths = set(after_files)
    added = sorted(after_paths - before_paths)
    deleted = sorted(before_paths - after_paths)
    modified = sorted(
        path
        for path in before_paths & after_paths
        if before_files[path].get("sha256") != after_files[path].get("sha256")
        or before_files[path].get("size") != after_files[path].get("size")
    )
    changed = sorted(set(added + deleted + modified))
    return {
        "added": added,
        "deleted": deleted,
        "modified": modified,
        "changed_paths": changed,
        "changed": bool(changed),
    }


def protected_change_report(before: dict, after: dict, allowed_writer: str) -> dict:
    diff = diff_snapshots(before, after)
    unauthorized = diff["changed"] and allowed_writer != "certifier"
    violations = []
    if unauthorized:
        violations.append(
            "protected files changed without certifier authority: "
            + ", ".join(diff["changed_paths"])
        )
    return {
        "guard_id": "protected_file_guard",
        "before_file_count": before.get("file_count", 0),
        "after_file_count": after.get("file_count", 0),
        "allowed_writer": allowed_writer,
        "changed_paths": diff["changed_paths"],
        "added": diff["added"],
        "deleted": diff["deleted"],
        "modified": diff["modified"],
        "unauthorized_change": unauthorized,
        "violations": violations,
    }


def read_status_values(run_dir: Path) -> dict:
    values = {}
    for name in STATUS_FILES:
        path = run_dir / name
        if not path.is_file():
            values[name] = "MISSING"
            continue
        if name.endswith(".json"):
            try:
                values[name] = json.loads(path.read_text(encoding="utf-8-sig")).get("status", "MISSING")
            except json.JSONDecodeError:
                values[name] = "MISSING"
        else:
            text = path.read_text(encoding="utf-8-sig").strip()
            match = STATUS_RE.search(text)
            values[name] = match.group(1) if match else "MISSING"
    return values


def statuses_agree(status_values: dict) -> bool:
    return (
        set(status_values) == set(STATUS_FILES)
        and "MISSING" not in status_values.values()
        and len(set(status_values.values())) == 1
    )
