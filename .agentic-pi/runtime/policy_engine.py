#!/usr/bin/env python3
"""Deterministic verifier-provenance certification policy engine."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROVENANCE_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
STRENGTH_ORDER = {"weak": 0, "advisory": 1, "gating": 2, "certifying": 3}

DEFAULT_POLICY = {
    "certifying_authority_levels": {"P2", "P3"},
    "provisional_authority_levels": {"P0", "P1"},
    "minimum_strength_level": "certifying",
    "disqualifying_smells_allowed": False,
}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def safe_report_filename(artifact_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in artifact_id)
    return f"{safe or 'UNKNOWN'}.json"


def resolve_run_path(run_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"absolute path is not allowed: {raw_path}")

    run_root = run_dir.resolve()
    resolved = (run_root / candidate).resolve()
    if resolved != run_root and run_root not in resolved.parents:
        raise ValueError(f"path escapes run folder: {raw_path}")
    return resolved


def target_artifact_exists(run_dir: Path, target: str) -> bool:
    try:
        return resolve_run_path(run_dir, target).is_file()
    except ValueError:
        return False


def load_verifier_artifacts(run_dir: Path) -> list:
    verifier_dir = run_dir / "verifier_artifacts"
    if not verifier_dir.exists():
        return []
    return [load_json(path) for path in sorted(verifier_dir.glob("*.json"))]


def load_reports_by_artifact_id(run_dir: Path, folder_name: str) -> dict:
    report_dir = run_dir / folder_name
    if not report_dir.exists():
        return {}

    reports = {}
    for report_path in sorted(report_dir.glob("*.json")):
        report = load_json(report_path)
        artifact_id = str(report.get("artifact_id") or "")
        if artifact_id:
            reports[artifact_id] = report
    return reports


def level_meets_required(level: str, required_level: str) -> bool:
    return PROVENANCE_ORDER.get(level, -1) >= PROVENANCE_ORDER.get(required_level, 99)


def strength_meets_required(strength_level: str, minimum_strength_level: str) -> bool:
    return STRENGTH_ORDER.get(strength_level, -1) >= STRENGTH_ORDER.get(
        minimum_strength_level, 99
    )


def effective_minimum_strength(contract: dict) -> str:
    contract_minimum = contract.get(
        "minimum_strength_level",
        DEFAULT_POLICY["minimum_strength_level"],
    )
    if STRENGTH_ORDER.get(contract_minimum, -1) > STRENGTH_ORDER["certifying"]:
        return contract_minimum
    return "certifying"


def artifact_id(artifact: dict) -> str:
    return str(artifact.get("artifact_id") or "UNKNOWN")


def artifact_rejection(artifact: dict, reason: str) -> str:
    return f"{artifact_id(artifact)}: {reason}"


def policy_decision(
    run_id: str,
    status: str,
    reason: str,
    required_verifier_level: str,
    certifying_artifacts=None,
    provisional_artifacts=None,
    rejected_artifacts=None,
    policy_checks=None,
) -> dict:
    return {
        "run_id": run_id,
        "status": status,
        "reason": reason,
        "required_verifier_level": required_verifier_level,
        "certifying_artifacts": certifying_artifacts or [],
        "provisional_artifacts": provisional_artifacts or [],
        "rejected_artifacts": rejected_artifacts or [],
        "policy_checks": policy_checks or [],
    }


def evaluate_artifact(
    artifact: dict,
    contract: dict,
    smell_report: dict,
    strength_report: dict,
) -> tuple:
    target_artifacts = set(contract.get("target_artifacts", []))
    required_level = contract.get("required_verifier_level", "P2")
    certifying_levels = set(
        contract.get(
            "certifying_authority_levels",
            DEFAULT_POLICY["certifying_authority_levels"],
        )
    )
    minimum_strength = effective_minimum_strength(contract)

    level = artifact.get("provenance_level")
    strength_level = (strength_report or {}).get("strength_level")
    checks = []

    if artifact.get("target_artifact") not in target_artifacts:
        return "rejected", artifact_rejection(
            artifact,
            "target_artifact does not match verifier_contract target_artifacts",
        ), checks
    checks.append("target artifact matches verifier contract")

    if level in DEFAULT_POLICY["provisional_authority_levels"]:
        if level == "P0":
            checks.append("P0 cannot certify DONE alone")
            return "provisional", artifact_id(artifact), checks
        if level == "P1":
            checks.append("P1 is provisional by default")
            return "provisional", artifact_id(artifact), checks

    if level not in certifying_levels:
        return "rejected", artifact_rejection(
            artifact,
            f"provenance level {level!r} is not a certifying authority level",
        ), checks
    checks.append(f"provenance level is {level}")

    if not level_meets_required(level, required_level):
        return "rejected", artifact_rejection(
            artifact,
            f"provenance level {level!r} is below required {required_level!r}",
        ), checks
    checks.append(f"provenance level meets required {required_level}")

    if artifact.get("authority") != "certifying":
        return "provisional", artifact_id(artifact), checks + [
            "verifier authority is not certifying"
        ]
    checks.append("verifier authority is certifying")

    if artifact.get("same_worker_as_solution") is True:
        return "provisional", artifact_id(artifact), checks + [
            "same_worker_as_solution prevents certification"
        ]
    checks.append("same_worker_as_solution is false")

    if not strength_report:
        return "provisional", artifact_id(artifact), checks + [
            "strength report missing"
        ]

    if not strength_meets_required(strength_level, minimum_strength):
        return "provisional", artifact_id(artifact), checks + [
            f"strength level {strength_level!r} is below required {minimum_strength!r}"
        ]
    checks.append(f"strength level is {strength_level}")

    if smell_report and smell_report.get("disqualifying") is True:
        return "provisional", artifact_id(artifact), checks + [
            "disqualifying smell prevents certification"
        ]
    checks.append("no disqualifying smell")

    return "certifying", artifact_id(artifact), checks


def decide_run_policy(run_dir: Path, hard_failures=None) -> dict:
    hard_failures = list(hard_failures or [])
    run_id = run_dir.name
    contract_path = run_dir / "verifier_contract.json"
    required_level = "P2"
    policy_checks = []

    if not contract_path.exists():
        return policy_decision(
            run_id=run_id,
            status="NOT_DONE",
            reason="verifier_contract.json is required for provenance policy mode.",
            required_verifier_level=required_level,
            rejected_artifacts=["verifier_contract.json missing"],
            policy_checks=["verifier contract missing"],
        )

    contract = load_json(contract_path)
    run_id = str(contract.get("run_id") or run_id)
    required_level = contract.get("required_verifier_level", "P2")
    policy_checks.append("verifier contract exists")

    if (
        PROVENANCE_ORDER.get(required_level, -1) >= PROVENANCE_ORDER["P2"]
        and contract.get("allow_self_generated_only") is True
    ):
        return policy_decision(
            run_id=run_id,
            status="NOT_DONE",
            reason=(
                "Verifier contract conflict: allow_self_generated_only must be false "
                "when P2 or P3 verifier authority is required."
            ),
            required_verifier_level=required_level,
            rejected_artifacts=["allow_self_generated_only conflicts with P2/P3 requirement"],
            policy_checks=policy_checks + ["self-generated-only policy conflict"],
        )

    target_artifacts = contract.get("target_artifacts", [])
    missing_targets = [
        target for target in target_artifacts if not target_artifact_exists(run_dir, target)
    ]
    if missing_targets:
        return policy_decision(
            run_id=run_id,
            status="NOT_DONE",
            reason="Verifier target artifact is missing.",
            required_verifier_level=required_level,
            rejected_artifacts=[f"missing target artifact: {target}" for target in missing_targets],
            policy_checks=policy_checks + ["target artifact missing"],
        )
    policy_checks.append("target artifact exists")

    try:
        artifacts = load_verifier_artifacts(run_dir)
    except Exception as exc:
        return policy_decision(
            run_id=run_id,
            status="NOT_DONE",
            reason="Verifier artifact could not be loaded.",
            required_verifier_level=required_level,
            rejected_artifacts=[f"invalid verifier artifact: {exc}"],
            policy_checks=policy_checks + ["verifier artifact invalid"],
        )
    if not artifacts:
        return policy_decision(
            run_id=run_id,
            status="NOT_DONE",
            reason="No verifier artifacts found for verifier_contract.json.",
            required_verifier_level=required_level,
            rejected_artifacts=[],
            policy_checks=policy_checks + ["verifier artifact missing"],
        )
    policy_checks.append("verifier artifact exists")

    if hard_failures:
        return policy_decision(
            run_id=run_id,
            status="NOT_DONE",
            reason="Hard validation failure exists before policy decision.",
            required_verifier_level=required_level,
            rejected_artifacts=[str(item) for item in hard_failures],
            policy_checks=policy_checks + ["hard validation failure blocks certification"],
        )

    smell_reports = load_reports_by_artifact_id(run_dir, "verifier_smell_reports")
    strength_reports = load_reports_by_artifact_id(run_dir, "verifier_strength_reports")
    certifying = []
    provisional = []
    rejected = []

    for artifact in artifacts:
        result, value, checks = evaluate_artifact(
            artifact,
            contract,
            smell_reports.get(artifact_id(artifact), {}),
            strength_reports.get(artifact_id(artifact), {}),
        )
        policy_checks.extend(checks)
        if result == "certifying":
            certifying.append(value)
        elif result == "provisional":
            provisional.append(value)
        else:
            rejected.append(value)

    if certifying:
        return policy_decision(
            run_id=run_id,
            status="CERTIFIED_DONE",
            reason=(
                "At least one P2/P3 verifier artifact has certifying strength "
                "and satisfies the verifier contract."
            ),
            required_verifier_level=required_level,
            certifying_artifacts=certifying,
            provisional_artifacts=provisional,
            rejected_artifacts=rejected,
            policy_checks=policy_checks,
        )

    if provisional:
        levels = sorted({str(artifact.get("provenance_level")) for artifact in artifacts})
        if levels == ["P0"]:
            reason = "P0 cannot certify DONE alone."
        elif levels == ["P1"]:
            reason = "P1 is provisional by default."
        else:
            reason = "Independent verifier exists, but verifier strength is insufficient."
        return policy_decision(
            run_id=run_id,
            status="PROVISIONAL_DONE",
            reason=reason,
            required_verifier_level=required_level,
            certifying_artifacts=[],
            provisional_artifacts=provisional,
            rejected_artifacts=rejected,
            policy_checks=policy_checks,
        )

    return policy_decision(
        run_id=run_id,
        status="NOT_DONE",
        reason="No verifier artifact satisfies the verifier contract target and authority rules.",
        required_verifier_level=required_level,
        certifying_artifacts=[],
        provisional_artifacts=[],
        rejected_artifacts=rejected,
        policy_checks=policy_checks,
    )


def write_policy_decision(run_dir: Path, decision: dict) -> Path:
    decision = dict(decision)
    decision["generated_at"] = datetime.now(timezone.utc).isoformat()
    path = run_dir / "policy_decision.json"
    write_json(path, decision)
    return path


def main():
    if len(sys.argv) != 2:
        print("Usage: python policy_engine.py <run_dir>")
        sys.exit(2)

    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print("RUN_DIR_MISSING")
        sys.exit(1)

    decision = decide_run_policy(run_dir)
    path = write_policy_decision(run_dir, decision)
    written_decision = load_json(path)
    print(json.dumps(written_decision, indent=2, ensure_ascii=False))
    print(f"Wrote {path}")
    if decision["status"] == "NOT_DONE":
        sys.exit(1)


if __name__ == "__main__":
    main()
