#!/usr/bin/env python3
"""Validate the multi-frame reasoning gate for one run.

This validator is deliberately reasoning-only. It rejects premature convergence,
weak frame/attack linkage, and authority overclaims. It does not certify final
DONE and must not write final-status artifacts.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / ".agentic-pi" / "schemas"
VALIDATE_SCHEMA_PATH = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"

REQUIRED_ARTIFACTS = {
    "frame_candidates": ("frame_candidates.json", "frame_candidates.schema.json"),
    "assumption_matrix": ("assumption_matrix.json", "assumption_matrix.schema.json"),
    "attack_report": ("attack_report.json", "attack_report.schema.json"),
    "selection_decision": ("selection_decision.json", "selection_decision.schema.json"),
    "reasoning_certification": ("reasoning_certification.json", "reasoning_certification.schema.json"),
}

PROTECTED_STATUS_ARTIFACTS = {
    "final_status.json",
    "final_status.md",
    "certification.json",
    "policy_decision.json",
}

FORBIDDEN_STATUS_VALUES = {
    "DONE",
    "DONE_PASS",
    "DONE_FAIL",
    "NOT_DONE",
    "PROVISIONAL_DONE",
    "CERTIFIED_DONE",
    "CERTIFIED_FAIL",
    "NEEDS_HUMAN_REVIEW",
}

INVISIBLE_CODEPOINTS = {
    "\u200b",  # zero width space
    "\u200c",  # zero width non-joiner
    "\u200d",  # zero width joiner
    "\ufeff",  # byte order mark / zero width no-break space
    "\u2060",  # word joiner
}

FORBIDDEN_CLAIM_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bi have certified\b",
        r"\bi am the certifier\b",
        r"\bmy output is authoritative\b",
        r"\bpolicy decision is final\b",
        r"\bverifier will accept my result without further checks\b",
        r"\bi certify\b.*\b(final|done|result|status)\b",
        r"\bcertify\b.*\b(final|done|result|status)\b",
        r"\bfinal\b.*\b(authority|authoritative|approved|certified)\b",
        r"\bauthoritative\b.*\b(final|status|result)\b",
    ]
]


class ReasoningGateValidationError(RuntimeError):
    """Raised when a reasoning gate artifact cannot be loaded."""


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_schema_validator():
    spec = importlib.util.spec_from_file_location("validate_schema_for_reasoning_gate", VALIDATE_SCHEMA_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def path_to_run_dir(path: Path) -> Path:
    if path.is_dir():
        return path
    return path.parent


def validate_run_dir_boundary(run_dir: Path) -> list[str]:
    """Require a direct .agentic-runs/<run_id> directory."""
    try:
        resolved = run_dir.resolve()
        runs_root = (ROOT / ".agentic-runs").resolve()
    except OSError as exc:
        return [f"failed to resolve run directory boundary: {exc}"]
    if resolved.parent != runs_root:
        return [f"run_path must resolve to a direct .agentic-runs/<run_id> directory, got {run_dir}"]
    return []


def strip_invisible_characters(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(
        char for char in normalized
        if char not in INVISIBLE_CODEPOINTS and unicodedata.category(char) != "Cf"
    )


def normalize_text(value: str) -> str:
    return " ".join(strip_invisible_characters(value).lower().split())


def is_clean_run_id(value: str) -> bool:
    return value == strip_invisible_characters(value).strip()


def recursively_scan_forbidden_values(value: Any, errors: list[str], loc: str = "$", *, key: str = "") -> None:
    if isinstance(value, dict):
        if value.get("can_certify_done") is True:
            errors.append(f"{loc}.can_certify_done: reasoning gate cannot certify DONE")
        for child_key, child in value.items():
            recursively_scan_forbidden_values(child, errors, f"{loc}.{child_key}", key=str(child_key))
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            recursively_scan_forbidden_values(child, errors, f"{loc}[{index}]", key=key)
        return
    if not isinstance(value, str):
        return

    scanned_value = strip_invisible_characters(value)
    if scanned_value in FORBIDDEN_STATUS_VALUES:
        errors.append(f"{loc}: reasoning gate must not contain final status value {value!r}")
    if key in {"status", "decision_status"} and scanned_value in FORBIDDEN_STATUS_VALUES:
        errors.append(f"{loc}: status field must not use final authority status {value!r}")
    for status_value in sorted(FORBIDDEN_STATUS_VALUES - {"DONE"}, key=len, reverse=True):
        if re.search(rf"\b{re.escape(status_value)}\b", scanned_value):
            errors.append(f"{loc}: reasoning text must not embed final status value {status_value!r}")
    for pattern in FORBIDDEN_CLAIM_PATTERNS:
        if pattern.search(scanned_value):
            errors.append(f"{loc}: forbidden authority claim {value!r}")


def validate_refs(refs: list[str], errors: list[str], loc: str) -> None:
    for ref in refs:
        ref_path = Path(ref)
        if ref_path.is_absolute() or ".." in ref_path.parts or ":" in ref or "\\" in ref:
            errors.append(f"{loc}: evidence ref must be run-relative and non-escaping, got {ref!r}")
        normalized_name = normalize_text(ref_path.name).replace(" ", "")
        normalized_stem = normalized_name.rsplit(".", 1)[0]
        protected_stems = {"final_status", "certification", "policy_decision"}
        protected_like = any(
            normalized_stem == stem or normalized_stem.startswith((f"{stem}_", f"{stem}-", f"{stem}."))
            for stem in protected_stems
        )
        if ref_path.name in PROTECTED_STATUS_ARTIFACTS or protected_like:
            errors.append(f"{loc}: evidence ref must not target protected status artifact {ref!r}")


def validate_reasoning_gate(data_by_name: dict[str, dict], *, run_dir: Path | None = None) -> list[str]:
    errors: list[str] = []
    schema_validator = load_schema_validator()

    for artifact_name, data in data_by_name.items():
        _, schema_file = REQUIRED_ARTIFACTS[artifact_name]
        schema = load_json(SCHEMA_DIR / schema_file)
        schema_errors = schema_validator.validate(data, schema)
        errors.extend(f"{artifact_name} schema: {item}" for item in schema_errors)
        recursively_scan_forbidden_values(data, errors, loc=f"{artifact_name}")

    if errors:
        return errors

    raw_run_ids = [data["run_id"] for data in data_by_name.values()]
    for run_id in raw_run_ids:
        if not is_clean_run_id(run_id):
            errors.append(f"run_id must not contain leading/trailing whitespace or invisible characters: {run_id!r}")
    run_ids = {strip_invisible_characters(run_id).strip() for run_id in raw_run_ids}
    if len(run_ids) != 1:
        errors.append(f"all reasoning artifacts must share one run_id, got {sorted(raw_run_ids)!r}")

    frames = data_by_name["frame_candidates"]["frames"]
    if len(frames) < 5:
        errors.append("frame_candidates.frames: multi-frame reasoning requires at least 5 frames")

    frame_by_id: dict[str, dict] = {}
    normalized_frames: dict[str, str] = {}
    for frame in frames:
        frame_id = frame["frame_id"]
        if frame_id in frame_by_id:
            errors.append(f"duplicate frame_id: {frame_id}")
        frame_by_id[frame_id] = frame
        normalized = normalize_text(f"{frame['title']} {frame['thesis']}")
        if normalized in normalized_frames:
            errors.append(f"duplicate normalized frame content: {normalized_frames[normalized]} and {frame_id}")
        normalized_frames[normalized] = frame_id

    assumptions = data_by_name["assumption_matrix"]["assumptions"]
    assumption_frame_ids: set[str] = set()
    assumption_ids: set[str] = set()
    for assumption in assumptions:
        assumption_id = assumption["assumption_id"]
        if assumption_id in assumption_ids:
            errors.append(f"duplicate assumption_id: {assumption_id}")
        assumption_ids.add(assumption_id)
        for frame_id in assumption["frame_ids"]:
            if frame_id not in frame_by_id:
                errors.append(f"assumption {assumption_id} references unknown frame_id {frame_id!r}")
            assumption_frame_ids.add(frame_id)
    for frame_id in frame_by_id:
        if frame_id not in assumption_frame_ids:
            errors.append(f"frame {frame_id} has no linked assumption in assumption_matrix")

    attacks = data_by_name["attack_report"]["attacks"]
    attack_ids: set[str] = set()
    attack_frame_ids: set[str] = set()
    attacks_by_frame: dict[str, list[dict]] = {frame_id: [] for frame_id in frame_by_id}
    for attack in attacks:
        attack_id = attack["attack_id"]
        if attack_id in attack_ids:
            errors.append(f"duplicate attack_id: {attack_id}")
        attack_ids.add(attack_id)
        frame_id = attack["target_frame_id"]
        if frame_id not in frame_by_id:
            errors.append(f"attack {attack_id} references unknown frame_id {frame_id!r}")
            continue
        attack_frame_ids.add(frame_id)
        attacks_by_frame[frame_id].append(attack)
    for frame_id in frame_by_id:
        if frame_id not in attack_frame_ids:
            errors.append(f"frame {frame_id} has no attack in attack_report")

    selection = data_by_name["selection_decision"]
    validate_refs(selection.get("evidence_refs", []), errors, "selection_decision.evidence_refs")
    if selection["decision_status"] != "FRAME_SELECTED":
        errors.append("selection_decision.decision_status must be FRAME_SELECTED for a passing reasoning gate")
    selected_frame_id = selection.get("selected_frame_id")
    if not selected_frame_id:
        errors.append("selection_decision.selected_frame_id is required when decision_status is FRAME_SELECTED")
    elif selected_frame_id not in frame_by_id:
        errors.append(f"selection_decision.selected_frame_id references unknown frame {selected_frame_id!r}")

    rejected = selection.get("rejected_frame_ids", [])
    rejected_set = set(rejected)
    if len(rejected) != len(rejected_set):
        errors.append("selection_decision.rejected_frame_ids contains duplicates")
    for frame_id in rejected_set:
        if frame_id not in frame_by_id:
            errors.append(f"selection_decision.rejected_frame_ids references unknown frame {frame_id!r}")
    if selected_frame_id in rejected_set:
        errors.append("selection_decision.selected_frame_id must not also be rejected")
    if selected_frame_id in frame_by_id:
        expected_rejected = set(frame_by_id) - {selected_frame_id}
        if rejected_set != expected_rejected:
            errors.append(
                "selection_decision.rejected_frame_ids must equal all non-selected frames; "
                f"expected {sorted(expected_rejected)!r}, got {sorted(rejected_set)!r}"
            )
        for attack in attacks_by_frame.get(selected_frame_id, []):
            if attack["severity"] == "blocking" and attack["resolution"] != "mitigated":
                errors.append(f"selected frame {selected_frame_id} has unresolved blocking attack {attack['attack_id']}")

    certification = data_by_name["reasoning_certification"]
    if certification["status"] != "CERTIFIED_REASONED":
        errors.append("reasoning_certification.status must be CERTIFIED_REASONED for a passing reasoning gate")
    validate_refs(certification.get("checked_artifacts", []), errors, "reasoning_certification.checked_artifacts")
    checked = set(certification.get("checked_artifacts", []))
    expected_checked = {filename for filename, _schema in REQUIRED_ARTIFACTS.values()}
    if not expected_checked.issubset(checked):
        errors.append(
            "reasoning_certification.checked_artifacts must list all reasoning gate artifacts; "
            f"missing {sorted(expected_checked - checked)!r}"
        )

    if run_dir is not None:
        for protected_name in PROTECTED_STATUS_ARTIFACTS:
            if (run_dir / protected_name).exists():
                errors.append(f"reasoning gate run folder must not contain protected status artifact {protected_name}")

    return errors


def load_reasoning_gate(run_dir: Path) -> tuple[dict[str, dict], list[str]]:
    errors: list[str] = []
    data_by_name: dict[str, dict] = {}
    for artifact_name, (filename, _schema_file) in REQUIRED_ARTIFACTS.items():
        path = run_dir / filename
        if not path.is_file():
            errors.append(f"missing required reasoning artifact: {filename}")
            continue
        try:
            data_by_name[artifact_name] = load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"failed to load {filename}: {exc}")
    return data_by_name, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate multi-frame reasoning gate artifacts for one run")
    parser.add_argument("run_path", help="Run directory or path inside a run directory")
    args = parser.parse_args(argv)

    run_dir = path_to_run_dir(Path(args.run_path))
    errors = validate_run_dir_boundary(run_dir)
    data_by_name: dict[str, dict] = {}
    if not errors:
        data_by_name, load_errors = load_reasoning_gate(run_dir)
        errors.extend(load_errors)
    if not errors:
        errors.extend(validate_reasoning_gate(data_by_name, run_dir=run_dir))

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: reasoning gate valid for {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
