#!/usr/bin/env python3
"""Validate prompt provenance artifacts.

Prompt provenance is advisory/provenance-only. It records prompt transformation
metadata and must never certify DONE or replace verifier evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VALID_SCHEMA_VERSION = "prompt_provenance_v1"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_dict(data: dict, key: str, errors: list[str]) -> dict:
    value = data.get(key)
    if not isinstance(value, dict):
        errors.append(f"{key} must be an object")
        return {}
    return value


def validate_prompt_provenance(data: dict, *, source: str = "<prompt_provenance>", root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"{source}: artifact must be a JSON object"]

    if data.get("schema_version") != VALID_SCHEMA_VERSION:
        errors.append(f"{source}: schema_version must be {VALID_SCHEMA_VERSION}")
    for field in ("artifact_id", "run_id", "created_at"):
        if not isinstance(data.get(field), str) or not data.get(field, "").strip():
            errors.append(f"{source}: {field} must be a non-empty string")

    authority = _require_dict(data, "authority", errors)
    if authority.get("authority_level") != "provenance_only":
        errors.append(f"{source}: authority.authority_level must be provenance_only")
    if authority.get("can_certify_done") is not False:
        errors.append(f"{source}: authority.can_certify_done must be false")
    if authority.get("not_evidence_for_done") is not True:
        errors.append(f"{source}: authority.not_evidence_for_done must be true")

    raw = _require_dict(data, "raw_prompt", errors)
    raw_text = raw.get("text")
    if not isinstance(raw_text, str) or not raw_text.strip():
        errors.append(f"{source}: raw_prompt.text must be non-empty")
    elif raw.get("sha256") != sha256_text(raw_text):
        errors.append(f"{source}: raw_prompt.sha256 does not match text")
    if raw.get("present") is not True:
        errors.append(f"{source}: raw_prompt.present must be true")

    execution = _require_dict(data, "execution_prompt", errors)
    execution_text = execution.get("text")
    if not isinstance(execution_text, str) or not execution_text.strip():
        errors.append(f"{source}: execution_prompt.text must be non-empty")
    elif execution.get("sha256") != sha256_text(execution_text):
        errors.append(f"{source}: execution_prompt.sha256 does not match text")
    if execution.get("present") is not True:
        errors.append(f"{source}: execution_prompt.present must be true")

    checks = _require_dict(data, "checks", errors)
    if checks.get("authority_files_written") is not False:
        errors.append(f"{source}: checks.authority_files_written must be false")
    if checks.get("goal_contract_json_valid") is not True:
        errors.append(f"{source}: checks.goal_contract_json_valid must be true")

    goal_contract = _require_dict(data, "goal_contract", errors)
    goal_path = goal_contract.get("path")
    if not isinstance(goal_path, str) or not goal_path.strip():
        errors.append(f"{source}: goal_contract.path must be non-empty")
    else:
        artifact_path = Path(source)
        run_dir = artifact_path.parent.parent if artifact_path.name.endswith(".json") else None
        if run_dir and run_dir.is_dir():
            concrete_goal_path = (run_dir / goal_path).resolve()
            try:
                concrete_goal_path.relative_to(run_dir.resolve())
            except ValueError:
                errors.append(f"{source}: goal_contract.path escapes run folder")
            expected_hash = sha256_file(concrete_goal_path)
            if expected_hash and goal_contract.get("sha256") != expected_hash:
                errors.append(f"{source}: goal_contract.sha256 does not match {goal_path}")

    compiler_files = _require_dict(data, "prompt_compiler_files", errors)
    for key in ("agent_prompt", "runtime_prompt"):
        entry = compiler_files.get(key)
        if not isinstance(entry, dict):
            errors.append(f"{source}: prompt_compiler_files.{key} must be an object")
            continue
        path_value = entry.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            errors.append(f"{source}: prompt_compiler_files.{key}.path must be non-empty")
            continue
        if entry.get("exists") is True:
            concrete = (root / path_value).resolve()
            try:
                concrete.relative_to(root.resolve())
            except ValueError:
                errors.append(f"{source}: prompt_compiler_files.{key}.path escapes repo root")
                continue
            expected_hash = sha256_file(concrete)
            if expected_hash and entry.get("sha256") != expected_hash:
                errors.append(f"{source}: prompt_compiler_files.{key}.sha256 does not match file")

    return errors


def iter_targets(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.glob("prompt_provenance/*.prompt.json")) + sorted(path.glob("*.prompt.json"))
    return []


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate prompt provenance artifacts")
    parser.add_argument("target", help="prompt provenance JSON file, prompt_provenance dir, or run dir")
    args = parser.parse_args(argv)

    target = Path(args.target)
    if not target.exists():
        print(f"PROMPT_PROVENANCE_INVALID: path not found: {target}")
        return 1

    files = iter_targets(target)
    if not files:
        print(f"PROMPT_PROVENANCE_INVALID: no *.prompt.json files found in {target}")
        return 1

    errors: list[str] = []
    for path in files:
        try:
            data = load_json(path)
        except Exception as exc:
            errors.append(f"{path}: cannot parse JSON: {exc}")
            continue
        errors.extend(validate_prompt_provenance(data, source=str(path)))

    if errors:
        print("PROMPT_PROVENANCE_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PROMPT_PROVENANCE_VALID")
    print(f"validated_artifacts={len(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
