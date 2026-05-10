#!/usr/bin/env python3
"""Validator that checks replay report matches policy decision.

This validator ensures that if the replay report says REPLAY_MISMATCH,
the policy decision and certification must not have been used for a
final status. If they were, the run has failed replay.
"""

import json
from pathlib import Path
from typing import Optional


def load_json(path: Path) -> Optional[dict]:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def validate_replay_matches_policy(run_dir: Path) -> dict:
    """Validate that the replay report is consistent with policy and certification.

    Returns:
    {
        "valid": bool,
        "verdict": str,  # "MATCH" | "MISMATCH" | "INCONCLUSIVE"
        "detail": str,
        "evidence": dict
    }
    """
    replay = load_json(run_dir / "replay_report.json")
    policy = load_json(run_dir / "policy_decision.json")
    certification = load_json(run_dir / "certification.json")
    final_status = load_json(run_dir / "final_status.json")

    if not replay:
        return {
            "valid": False,
            "verdict": "MISMATCH",
            "detail": "No replay_report.json found",
            "evidence": {},
        }

    replay_verdict = replay.get("verdict", "REPLAY_MISMATCH")

    if replay_verdict == "REPLAY_MISMATCH":
        # If replay says mismatch, the policy and certification should also indicate
        # that the run is NOT clean
        policy_status = policy.get("status", "NOT_DONE") if policy else "NOT_DONE"
        cert_status = certification.get("status", "NOT_DONE") if certification else "NOT_DONE"
        final_status_status = final_status.get("status", "NOT_DONE") if final_status else "NOT_DONE"

        # If all three agree on NOT_DONE, the mismatch is expected (run genuinely failed)
        all_not_done = all(
            s in ("NOT_DONE", "FAILED") for s in [policy_status, cert_status, final_status_status]
        )
        if all_not_done:
            return {
                "valid": True,
                "verdict": "MATCH",
                "detail": "Replay mismatch expected: all statuses are NOT_DONE/FAILED",
                "evidence": {
                    "replay_verdict": replay_verdict,
                    "policy_status": policy_status,
                    "cert_status": cert_status,
                    "final_status": final_status_status,
                },
            }
        else:
            return {
                "valid": False,
                "verdict": "MISMATCH",
                "detail": f"Replay reports MISMATCH but statuses indicate completion: "
                         f"policy={policy_status}, cert={cert_status}, final={final_status_status}",
                "evidence": {
                    "replay_verdict": replay_verdict,
                    "policy_status": policy_status,
                    "cert_status": cert_status,
                    "final_status": final_status_status,
                },
            }

    # Replay MATCH or PARTIAL: check that policy and certification agree
    if policy and certification:
        policy_status = policy.get("status", "")
        cert_status = certification.get("status", "")
        if policy_status != cert_status:
            return {
                "valid": False,
                "verdict": "MISMATCH",
                "detail": f"Policy and certification disagree despite replay match: "
                         f"policy={policy_status}, cert={cert_status}",
                "evidence": {
                    "replay_verdict": replay_verdict,
                    "policy_status": policy_status,
                    "cert_status": cert_status,
                },
            }

    return {
        "valid": True,
        "verdict": "MATCH",
        "detail": "Replay, policy, and certification are consistent",
        "evidence": {
            "replay_verdict": replay_verdict,
            "policy_status": policy.get("status", "") if policy else "N/A",
            "cert_status": certification.get("status", "") if certification else "N/A",
        },
    }
