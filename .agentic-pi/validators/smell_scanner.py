#!/usr/bin/env python3
"""Scan verifier provenance artifacts for metadata-level verifier smells."""
import json
import sys
from pathlib import Path


DISQUALIFYING_FLAGS = {
    "does_not_execute_code",
    "zero_assertions",
}

FLAG_PENALTIES = {
    "same_worker_self_test": 2,
    "post_solution_test": 1,
    "depends_on_solution": 1,
    "does_not_execute_code": 3,
    "zero_assertions": 3,
    "mock_heavy": 2,
    "p0_self_authored": 2,
    "advisory_only": 1,
    "local_visible_verifier": 1,
    "gating_only": 1,
    "file_existence_only": 2,
    "exit_code_only": 2,
    "print_only_observation": 2,
    "grep_or_source_text_check": 2,
    "no_negative_case": 1,
    "implementation_coupled_oracle": 3,
    "placeholder_text_check": 2,
}

PASSTHROUGH_FLAGS = {
    "file_existence_only",
    "exit_code_only",
    "print_only_observation",
    "grep_or_source_text_check",
    "no_negative_case",
    "implementation_coupled_oracle",
    "placeholder_text_check",
}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def safe_report_filename(artifact_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in artifact_id)
    return f"{safe or 'UNKNOWN'}.json"


def add_flag(flags, flag):
    if flag not in flags:
        flags.append(flag)


def scan_verifier_artifact(artifact: dict) -> dict:
    flags = []

    if artifact.get("same_worker_as_solution") is True or artifact.get("source") == "same_run_worker":
        add_flag(flags, "same_worker_self_test")

    if artifact.get("created_at_phase") == "post_solution":
        add_flag(flags, "post_solution_test")

    if artifact.get("depends_on_solution") is True:
        add_flag(flags, "depends_on_solution")

    if artifact.get("executes_code") is not True:
        add_flag(flags, "does_not_execute_code")

    if not isinstance(artifact.get("assertion_count"), int) or artifact.get("assertion_count", 0) <= 0:
        add_flag(flags, "zero_assertions")

    if isinstance(artifact.get("mock_ratio_percent"), int) and artifact["mock_ratio_percent"] >= 50:
        add_flag(flags, "mock_heavy")

    if artifact.get("provenance_level") == "P0":
        add_flag(flags, "p0_self_authored")

    if artifact.get("authority") == "advisory":
        add_flag(flags, "advisory_only")

    if artifact.get("source") in {"existing_repo_test", "same_run_verifier_agent"}:
        add_flag(flags, "local_visible_verifier")

    if artifact.get("authority") == "gating":
        add_flag(flags, "gating_only")

    for existing in artifact.get("smell_flags", []):
        if existing in PASSTHROUGH_FLAGS:
            add_flag(flags, existing)

    return {
        "artifact_id": artifact.get("artifact_id", ""),
        "smell_flags": flags,
        "disqualifying": any(flag in DISQUALIFYING_FLAGS for flag in flags),
        "authority_penalty": sum(FLAG_PENALTIES.get(flag, 0) for flag in flags),
    }


def scan_artifact_file(path: Path) -> dict:
    return scan_verifier_artifact(load_json(path))


def scan_run_dir(run_dir: Path) -> list:
    verifier_dir = run_dir / "verifier_artifacts"
    if not verifier_dir.exists():
        return []
    return [scan_artifact_file(path) for path in sorted(verifier_dir.glob("*.json"))]


def main():
    if len(sys.argv) not in {2, 3}:
        print("Usage: python smell_scanner.py <verifier_artifact.json|run_dir> [output_dir]")
        sys.exit(2)

    input_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) == 3 else None

    if input_path.is_dir():
        reports = scan_run_dir(input_path)
    else:
        reports = [scan_artifact_file(input_path)]

    if output_dir:
        for report in reports:
            write_json(output_dir / safe_report_filename(report["artifact_id"]), report)

    print(json.dumps(reports, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
