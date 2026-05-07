#!/usr/bin/env python3
"""Aggregate v1.6 tool-use audit reports into a trajectory score."""

from __future__ import annotations

import argparse
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


def score_band(score: int) -> str:
    if score >= 90:
        return "excellent"
    if score >= 70:
        return "passing"
    return "failing"


def score_reports(reports: list[dict]) -> dict:
    scores = [report["metrics"]["score"] for report in reports]
    average_score = int(round(sum(scores) / len(scores))) if scores else 0
    failing = [report for report in reports if report["trajectory_status"] != "PASS"]
    return {
        "generated_by": "session-trace-scorer-v1.6",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
        "trajectory_status": "PASS" if not failing else "FAIL",
        "score": average_score,
        "score_band": score_band(average_score),
        "case_count": len(reports),
        "passed_count": len(reports) - len(failing),
        "failed_count": len(failing),
        "cases": [
            {
                "run_id": report["run_id"],
                "trajectory_status": report["trajectory_status"],
                "score": report["metrics"]["score"],
                "score_band": report["metrics"]["score_band"],
                "violations": report["violations"],
            }
            for report in reports
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Score one or more tool-use audit reports.")
    parser.add_argument("audit_reports", nargs="+")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    reports = [load_json(Path(path)) for path in args.audit_reports]
    score = score_reports(reports)
    rendered = json.dumps(score, indent=2, ensure_ascii=False)
    if args.output:
        write_json(Path(args.output), score)
    print(rendered)
    return 0 if score["trajectory_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
