#!/usr/bin/env python3
"""Run v1.6 trajectory-level diagnostic evaluation."""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DIAGNOSTIC_DIR = Path(__file__).resolve().parent
CASES_DIR = DIAGNOSTIC_DIR / "cases"
DEFAULT_OUTPUT_DIR = ROOT / "diagnostic_outputs"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool_use_audit = load_module("tool_use_audit_for_trajectory_eval", ROOT / ".agentic-pi" / "evaluation" / "tool_use_audit.py")
session_trace_scorer = load_module("session_trace_scorer_for_trajectory_eval", ROOT / ".agentic-pi" / "evaluation" / "session_trace_scorer.py")


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_report(metrics: dict) -> str:
    lines = [
        "# v1.6 Trajectory-Level Evaluation Report",
        "",
        f"Generated on {metrics['generated_at']}",
        f"Total cases: {metrics['total_cases']}",
        "",
        "## Case Matrix",
        "",
        "| Case | Expected | Observed | Score | Key Violations |",
        "|---|---|---|---:|---|",
    ]
    for row in metrics["cases"]:
        violations = "; ".join(row["violations"]) if row["violations"] else "none"
        lines.append(
            "| {case} | {expected} | {observed} | {score} | {violations} |".format(
                case=row["case_id"],
                expected=row["expected_trajectory_status"],
                observed=row["trajectory_status"],
                score=row["score"],
                violations=violations,
            )
        )

    lines.extend([
        "",
        "## Metrics",
        "",
        f"Status match rate: {metrics['status_match_rate']:.3f}",
        f"Unsafe trajectory count: {metrics['unsafe_trajectory_count']}",
        f"Average score: {metrics['score_report']['score']}",
        "",
        "## Claim Boundary",
        "",
        "This diagnostic evaluates tool/action trajectories only. It does not certify DONE, generate verifier artifacts, or replace certify_run.py / policy_engine.py.",
    ])
    return "\n".join(lines) + "\n"


def run_evaluation(output_dir: Path) -> dict:
    manifest = load_json(DIAGNOSTIC_DIR / "manifest.json")
    rows = []
    audit_reports = []
    for case_id, case in manifest["cases"].items():
        session_path = CASES_DIR / f"{case_id}.jsonl"
        audit = tool_use_audit.audit_tool_use(session_path, case["run_id"])
        audit_reports.append(audit)
        rows.append({
            "case_id": case_id,
            "run_id": case["run_id"],
            "expected_trajectory_status": case["expected_trajectory_status"],
            "trajectory_status": audit["trajectory_status"],
            "score": audit["metrics"]["score"],
            "score_band": audit["metrics"]["score_band"],
            "violations": audit["violations"],
            "status_match": audit["trajectory_status"] == case["expected_trajectory_status"],
        })

    score_report = session_trace_scorer.score_reports(audit_reports)
    metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_id": manifest["diagnostic_id"],
        "version": manifest["version"],
        "total_cases": len(rows),
        "status_match_rate": len([row for row in rows if row["status_match"]]) / len(rows),
        "unsafe_trajectory_count": len([row for row in rows if row["trajectory_status"] == "FAIL"]),
        "cases": rows,
        "score_report": score_report,
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "trajectory_metrics.json", metrics)
    (output_dir / "trajectory_report.md").write_text(build_report(metrics), encoding="utf-8")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v1.6 trajectory-level diagnostic evaluation.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()
    metrics = run_evaluation(Path(args.output_dir))
    print(
        "Trajectory evaluation complete. "
        f"Status match rate = {metrics['status_match_rate']:.3f}; "
        f"unsafe trajectories = {metrics['unsafe_trajectory_count']}"
    )
    print(f"Wrote {Path(args.output_dir) / 'trajectory_metrics.json'}")
    print(f"Wrote {Path(args.output_dir) / 'trajectory_report.md'}")
    return 0 if metrics["status_match_rate"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
