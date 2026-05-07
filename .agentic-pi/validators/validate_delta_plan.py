#!/usr/bin/env python3
"""Validate delta_plan.json safety boundaries."""
import argparse
import json
import sys
from pathlib import Path


PROTECTED_NAMES = {"final_status.md", "certification.json", "policy_decision.json"}
PROTECTED_PREFIXES = {"verifier_artifacts/", "verifier_smell_reports/", "verifier_strength_reports/"}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_run_path(run_dir: Path, raw_path: str) -> str:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"absolute delta path rejected: {raw_path}")
    root = run_dir.resolve()
    resolved = (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"delta path escapes run folder: {raw_path}")
    return resolved.relative_to(root).as_posix()


def protected_violation(rel_path: str) -> str:
    if Path(rel_path).name in PROTECTED_NAMES:
        return f"protected status artifact write rejected: {rel_path}"
    if any(rel_path == prefix.rstrip("/") or rel_path.startswith(prefix) for prefix in PROTECTED_PREFIXES):
        return f"protected verifier provenance write rejected: {rel_path}"
    return ""


def validate_delta_plan(run_dir: Path) -> dict:
    delta_path = run_dir / "delta_plan.json"
    delta = load_json(delta_path)
    violations = []
    checks = []

    if delta.get("final_status_authority") != "certifier_only":
        violations.append("delta_plan.json must keep final_status_authority=certifier_only")
    if delta.get("decision_status") not in {"NO_DELTA_NEEDED", "DELTA_PLAN_CREATED", "ABORT_REQUIRES_USER"}:
        violations.append(f"unknown delta decision_status: {delta.get('decision_status')!r}")

    for index, step in enumerate(delta.get("delta_steps", []), start=1):
        if step.get("action") != "create_file":
            violations.append(f"delta step {index} unsupported action: {step.get('action')!r}")
            continue
        raw_path = step.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            violations.append(f"delta step {index} missing path")
            continue
        try:
            rel_path = resolve_run_path(run_dir, raw_path)
        except ValueError as exc:
            violations.append(str(exc))
            continue
        protected = protected_violation(rel_path)
        if protected:
            violations.append(protected)
        else:
            checks.append(f"delta step {index} path accepted: {rel_path}")

        for produced_index, produced in enumerate(step.get("produces", []), start=1):
            produced_path = produced.get("path")
            if not isinstance(produced_path, str) or not produced_path.strip():
                violations.append(f"delta step {index} produces[{produced_index}] missing path")
                continue
            try:
                produced_rel = resolve_run_path(run_dir, produced_path)
            except ValueError as exc:
                violations.append(str(exc))
                continue
            protected = protected_violation(produced_rel)
            if protected:
                violations.append(protected)

    report = {
        "run_id": delta.get("run_id", run_dir.name),
        "valid": not violations,
        "checks": checks,
        "violations": violations,
    }
    write_json(run_dir / "delta_plan_validation.json", report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate delta_plan.json safety.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    try:
        report = validate_delta_plan(Path(args.run_dir))
    except Exception as exc:
        print(f"DELTA_PLAN_VALIDATION_FAILED: {exc}")
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
