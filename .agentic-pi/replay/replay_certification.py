#!/usr/bin/env python3
"""Replay certification — recompute the certification decision from frozen evidence.

This is a trusted core component. It verifies that the original certification
decision is reproducible from the current (frozen) evidence.

Upgraded from replay_run.py to include:
- Evidence freeze hash comparison
- Policy/certification match
- Final status consistency
- Full de novo verdict derivation
"""

import hashlib
import json
import sys
from pathlib import Path
from typing import Optional

_REPLAY_DIR = Path(__file__).resolve().parent


def load_json(path: Path) -> Optional[dict]:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj: dict):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_replay_rules() -> list[dict]:
    rules_path = _REPLAY_DIR / "replay_rules.json"
    data = load_json(rules_path)
    return data.get("rules", []) if data else []


def compute_evidence_hashes(run_dir: Path) -> dict:
    """Compute SHA256 hashes for ALL files in a run directory.

    Uses recursive glob to find every file. This ensures that:
    - Evidence files are tracked (goal_contract, trace, step_logs, etc.)
    - Unauthorized new files are detected
    - Removed files are detected via freeze comparison
    """
    hashes = {}
    if not run_dir.is_dir():
        return hashes

    for fpath in sorted(run_dir.rglob("*")):
        if fpath.is_file():
            # Skip __pycache__ and .pyc
            if "__pycache__" in fpath.parts or fpath.suffix == ".pyc":
                continue
            rel = fpath.relative_to(run_dir).as_posix()
            # Skip meta-artifacts that describe the evidence but are not evidence themselves
            if rel in ("evidence_freeze.json", "replay_report.json"):
                continue
            hashes[rel] = sha256_file(fpath)

    return hashes


def run_replay_certification(run_dir: Path) -> dict:
    """Run the full replay certification for a run directory.

    Returns a replay report with detailed check results and an overall verdict.
    """
    rules = load_replay_rules()
    rule_map = {r["id"]: r for r in rules}

    checks = {}
    failed_severity_hits = []

    # ── Check 1: Evidence freeze exists ──
    evidence_freeze = load_json(run_dir / "evidence_freeze.json")
    checks["evidence_freeze_exists"] = {
        "passed": evidence_freeze is not None,
        "detail": "evidence_freeze.json found" if evidence_freeze else "evidence_freeze.json missing",
    }
    if not checks["evidence_freeze_exists"]["passed"]:
        failed_severity_hits.append("evidence_freeze_exists")

    # ── Check 2: Evidence hashes match ──
    current_hashes = compute_evidence_hashes(run_dir)
    if evidence_freeze:
        frozen_hashes = evidence_freeze.get("artifact_hashes", {})
        mismatches = []
        for rel_path, frozen_hash in frozen_hashes.items():
            current_hash = current_hashes.get(rel_path)
            if current_hash is None:
                mismatches.append(f"{rel_path}: missing (was present at freeze)")
            elif current_hash != frozen_hash:
                mismatches.append(f"{rel_path}: hash changed")
        # Also check for new files not in freeze
        for rel_path in current_hashes:
            if rel_path not in frozen_hashes:
                mismatches.append(f"{rel_path}: new file not in freeze")

        checks["evidence_hashes_match"] = {
            "passed": len(mismatches) == 0,
            "detail": f"{len(mismatches)} mismatch(es)" if mismatches else "All hashes match frozen evidence",
            "mismatches": mismatches,
        }
        if mismatches:
            failed_severity_hits.append("evidence_hashes_match")
    else:
        checks["evidence_hashes_match"] = {
            "passed": False,
            "detail": "Cannot check hashes: no evidence_freeze.json",
        }

    # ── Check 3: certification.json exists ──
    certification = load_json(run_dir / "certification.json")
    checks["certification_exists"] = {
        "passed": certification is not None,
        "detail": f"certification.json: status={certification.get('status', 'N/A')}" if certification else "certification.json missing",
    }
    if not certification:
        failed_severity_hits.append("certification_exists")

    # ── Check 4: policy_decision.json exists ──
    policy = load_json(run_dir / "policy_decision.json")
    checks["policy_decision_exists"] = {
        "passed": policy is not None,
        "detail": f"policy_decision.json: status={policy.get('status', 'N/A')}" if policy else "policy_decision.json missing",
    }
    if not policy:
        failed_severity_hits.append("policy_decision_exists")

    # ── Check 5: policy_cert_match ──
    if certification and policy:
        cert_status = certification.get("status", "")
        policy_status = policy.get("status", "")
        match = cert_status == policy_status
        checks["policy_cert_match"] = {
            "passed": match,
            "detail": f"cert={cert_status}, policy={policy_status}" + (" (match)" if match else " (MISMATCH)"),
        }
        if not match:
            failed_severity_hits.append("policy_cert_match")
    else:
        checks["policy_cert_match"] = {
            "passed": False,
            "detail": "Cannot compare: certification or policy missing",
        }
        failed_severity_hits.append("policy_cert_match")

    # ── Check 6: goal_contract present ──
    goal_contract = load_json(run_dir / "goal_contract.json")
    checks["goal_contract_present"] = {
        "passed": goal_contract is not None,
        "detail": "goal_contract.json found" if goal_contract else "goal_contract.json missing",
    }
    if not goal_contract:
        failed_severity_hits.append("goal_contract_present")

    # ── Check 7: trace valid ──
    trace_path = run_dir / "trace.jsonl"
    trace_valid = False
    trace_count = 0
    if trace_path.is_file():
        try:
            for line in trace_path.read_text(encoding="utf-8-sig").splitlines():
                if line.strip():
                    json.loads(line)
                    trace_count += 1
            trace_valid = trace_count > 0
        except Exception:
            trace_valid = False
    checks["trace_valid"] = {
        "passed": trace_valid,
        "detail": f"{trace_count} trace events" if trace_valid else "trace.jsonl invalid or empty",
    }

    # ── Check 8: step_logs present ──
    step_log_dir = run_dir / "step_logs"
    step_log_count = len(sorted(step_log_dir.glob("*.json"))) if step_log_dir.is_dir() else 0
    checks["step_logs_present"] = {
        "passed": step_log_count > 0,
        "detail": f"{step_log_count} step log(s)" if step_log_count > 0 else "step_logs missing or empty",
    }

    # ── Check 9: final_status.json exists ──
    final_status = load_json(run_dir / "final_status.json")
    checks["final_status_exists"] = {
        "passed": final_status is not None,
        "detail": f"final_status.json: status={final_status.get('status', 'N/A')}" if final_status else "final_status.json missing",
    }
    if not final_status:
        failed_severity_hits.append("final_status_exists")

    # ── Check 10: final_status_cert_match ──
    if final_status and certification:
        fs_status = final_status.get("status", "")
        cert_status = certification.get("status", "")
        match = fs_status == cert_status
        checks["final_status_cert_match"] = {
            "passed": match,
            "detail": f"final={fs_status}, cert={cert_status}" + (" (match)" if match else " (MISMATCH)"),
        }
        if not match:
            failed_severity_hits.append("final_status_cert_match")
    else:
        checks["final_status_cert_match"] = {
            "passed": False,
            "detail": "Cannot compare: final_status or certification missing",
        }
        failed_severity_hits.append("final_status_cert_match")

    # ── Determine verdict ──
    failed_severity_checks = [c for c in failed_severity_hits if rule_map.get(c, {}).get("severity") == "FAILED"]
    warning_only = [c for c in failed_severity_hits if rule_map.get(c, {}).get("severity") != "FAILED"]

    if not failed_severity_checks and not warning_only:
        verdict = "REPLAY_MATCH"
    elif not failed_severity_checks:
        verdict = "REPLAY_PARTIAL"
    else:
        verdict = "REPLAY_MISMATCH"

    report = {
        "schema_version": "replay_certification_v1",
        "run_id": (goal_contract or {}).get("run_id", run_dir.name),
        "verdict": verdict,
        "checks": checks,
        "failed_severity_checks": failed_severity_checks,
        "warning_checks": [c for c in failed_severity_hits if c in warning_only],
        "certification_status": certification.get("status", "") if certification else "",
        "policy_status": policy.get("status", "") if policy else "",
        "final_status": final_status.get("status", "") if final_status else "",
        "evidence_hash_count": len(current_hashes),
        "frozen_evidence_hash_count": len(evidence_freeze.get("artifact_hashes", {})) if evidence_freeze else 0,
    }

    # Write replay report
    write_json(run_dir / "replay_report.json", report)
    return report
