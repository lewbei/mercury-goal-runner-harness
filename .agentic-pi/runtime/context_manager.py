#!/usr/bin/env python3
"""Context management for long-running tasks.

Tracks context window usage and provides mechanisms for summarizing
old context when approaching limits. This addresses the performance
degradation issue identified in research (performance degrades after
35 minutes of human time).

The context manager:
1. Tracks context window usage
2. Summarizes old context when approaching limits
3. Provides context refresh mechanism
4. Logs context metrics

It does NOT certify DONE. It does NOT write final_status.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = ROOT / ".agentic-runs"
STATUS_ARTIFACTS = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}


class ContextManagerError(RuntimeError):
    """Raised when context manager cannot continue safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any = None) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        if default is not None:
            return default
        raise


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def resolve_run_dir(raw: str | None, run_id: str | None) -> Path:
    if raw:
        p = Path(raw)
        if p.is_dir():
            return p.resolve()
    if run_id:
        p = RUNS_ROOT / run_id
        if p.is_dir():
            return p.resolve()
    raise ContextManagerError("Provide --run-dir or --run-id with an existing run folder.")


def estimate_tokens(text: str) -> int:
    """Estimate token count (rough approximation: 1 token ≈ 4 chars)."""
    return len(text) // 4


def estimate_file_tokens(file_path: Path) -> int:
    """Estimate token count for a file."""
    if not file_path.exists():
        return 0
    try:
        content = file_path.read_text(encoding="utf-8")
        return estimate_tokens(content)
    except Exception:
        return 0


def scan_context_files(run_dir: Path) -> list[dict]:
    """Scan run directory for context files."""
    context_files = []
    
    # Key context files
    key_files = [
        "goal_contract.json",
        "run_state.json",
        "merged_plan.json",
        "expected_artifacts.json",
        "success_criteria_set.json",
        "adaptive_research_inputs.json",
        "planning_search_tree.json",
        "planning_coverage.json",
    ]
    
    for filename in key_files:
        file_path = run_dir / filename
        if file_path.exists():
            tokens = estimate_file_tokens(file_path)
            context_files.append({
                "filename": filename,
                "path": str(file_path),
                "tokens": tokens,
                "size_bytes": file_path.stat().st_size,
                "category": "key_context",
            })
    
    # Step logs
    step_logs_dir = run_dir / "step_logs"
    if step_logs_dir.exists():
        for log_file in step_logs_dir.glob("*.json"):
            tokens = estimate_file_tokens(log_file)
            context_files.append({
                "filename": f"step_logs/{log_file.name}",
                "path": str(log_file),
                "tokens": tokens,
                "size_bytes": log_file.stat().st_size,
                "category": "step_log",
            })
    
    # Artifacts
    artifacts_dir = run_dir / "artifacts"
    if artifacts_dir.exists():
        for artifact_file in artifacts_dir.rglob("*"):
            if artifact_file.is_file():
                tokens = estimate_file_tokens(artifact_file)
                context_files.append({
                    "filename": f"artifacts/{artifact_file.relative_to(artifacts_dir)}",
                    "path": str(artifact_file),
                    "tokens": tokens,
                    "size_bytes": artifact_file.stat().st_size,
                    "category": "artifact",
                })
    
    return context_files


def calculate_context_usage(context_files: list[dict]) -> dict:
    """Calculate context window usage."""
    total_tokens = sum(f["tokens"] for f in context_files)
    total_bytes = sum(f["size_bytes"] for f in context_files)
    
    # Group by category
    by_category = {}
    for f in context_files:
        cat = f["category"]
        if cat not in by_category:
            by_category[cat] = {"tokens": 0, "bytes": 0, "count": 0}
        by_category[cat]["tokens"] += f["tokens"]
        by_category[cat]["bytes"] += f["size_bytes"]
        by_category[cat]["count"] += 1
    
    return {
        "total_tokens": total_tokens,
        "total_bytes": total_bytes,
        "file_count": len(context_files),
        "by_category": by_category,
    }


def generate_context_summary(context_files: list[dict], usage: dict) -> dict:
    """Generate context summary for reporting."""
    # Sort by tokens (largest first)
    sorted_files = sorted(context_files, key=lambda f: f["tokens"], reverse=True)
    
    # Top consumers
    top_consumers = sorted_files[:10]
    
    # Recommendations
    recommendations = []
    
    # Check if approaching limits
    # Typical context windows: 128k-200k tokens
    # Warning at 50% (64k tokens)
    # Critical at 80% (128k tokens)
    warning_threshold = 64000
    critical_threshold = 128000
    
    if usage["total_tokens"] > critical_threshold:
        recommendations.append({
            "priority": "HIGH",
            "action": "summarize_context",
            "reason": f"Context usage critical: {usage['total_tokens']} tokens (>{critical_threshold})",
            "suggestion": "Summarize old step logs and artifacts to reduce context size",
        })
    elif usage["total_tokens"] > warning_threshold:
        recommendations.append({
            "priority": "MEDIUM",
            "action": "monitor_context",
            "reason": f"Context usage warning: {usage['total_tokens']} tokens (>{warning_threshold})",
            "suggestion": "Monitor context usage and prepare to summarize if needed",
        })
    
    # Check for large files
    for f in top_consumers[:3]:
        if f["tokens"] > 10000:
            recommendations.append({
                "priority": "LOW",
                "action": "summarize_file",
                "reason": f"Large file: {f['filename']} ({f['tokens']} tokens)",
                "suggestion": f"Consider summarizing {f['filename']} if not needed in full",
            })
    
    return {
        "timestamp": utc_now(),
        "usage": usage,
        "top_consumers": top_consumers,
        "recommendations": recommendations,
        "needs_action": len(recommendations) > 0,
    }


def run_context_manager(run_dir: Path) -> dict:
    """Run context management analysis."""
    # Scan context files
    context_files = scan_context_files(run_dir)
    
    # Calculate usage
    usage = calculate_context_usage(context_files)
    
    # Generate summary
    summary = generate_context_summary(context_files, usage)
    
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Context management for long-running tasks.")
    parser.add_argument("--run-dir", help="Path to the run directory")
    parser.add_argument("--run-id", help="Run identifier (resolved under .agentic-runs/)")
    parser.add_argument("--output", help="Output path for context summary JSON")
    args = parser.parse_args(argv)

    try:
        run_dir = resolve_run_dir(args.run_dir, args.run_id)
    except ContextManagerError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Run context manager
    summary = run_context_manager(run_dir)
    
    # Write summary
    output_path = Path(args.output) if args.output else run_dir / "context_summary.json"
    write_json(output_path, summary)
    
    # Print summary
    usage = summary["usage"]
    print(f"Context usage: {usage['total_tokens']} tokens ({usage['file_count']} files)")
    print(f"  Key context: {usage['by_category'].get('key_context', {}).get('tokens', 0)} tokens")
    print(f"  Step logs: {usage['by_category'].get('step_log', {}).get('tokens', 0)} tokens")
    print(f"  Artifacts: {usage['by_category'].get('artifact', {}).get('tokens', 0)} tokens")
    
    if summary["needs_action"]:
        print(f"\nRecommendations ({len(summary['recommendations'])}):")
        for rec in summary["recommendations"]:
            print(f"  [{rec['priority']}] {rec['action']}: {rec['reason']}")
    else:
        print("\nNo action needed.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
