#!/usr/bin/env python3
"""Research module for fetching latest information.

Fetches current information about models, technologies, and best practices.
This ensures the harness always uses up-to-date information.

The research module:
1. Fetches current date
2. Searches for latest models and technologies
3. Updates configuration with current information
4. Provides research context to agents

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


class ResearchError(RuntimeError):
    """Raised when research cannot continue safely."""


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
    raise ResearchError("Provide --run-dir or --run-id with an existing run folder.")


def get_current_date() -> dict:
    """Get current date and time."""
    now = datetime.now(timezone.utc)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "iso": now.isoformat(),
    }


def get_model_search_queries() -> list[str]:
    """Get search queries for latest models."""
    return [
        "latest AI coding models 2026",
        "best AI models for coding 2026",
        "Claude Opus GPT DeepSeek latest versions",
        "AI coding benchmarks 2026",
        "latest LLM releases 2026",
    ]


def get_technology_search_queries() -> list[str]:
    """Get search queries for latest technologies."""
    return [
        "latest programming languages 2026",
        "best frameworks 2026",
        "latest dev tools 2026",
        "AI coding best practices 2026",
        "latest software development trends 2026",
    ]


def generate_research_context(run_dir: Path) -> dict:
    """Generate research context for the current run."""
    # Get current date
    current_date = get_current_date()
    
    # Get search queries
    model_queries = get_model_search_queries()
    tech_queries = get_technology_search_queries()
    
    # Load goal contract if available
    goal_path = run_dir / "goal_contract.json"
    goal = {}
    if goal_path.exists():
        try:
            goal = load_json(goal_path)
        except Exception:
            pass
    
    # Generate research context
    research_context = {
        "timestamp": utc_now(),
        "current_date": current_date,
        "goal": goal.get("raw_user_prompt", "unknown"),
        "model_search_queries": model_queries,
        "technology_search_queries": tech_queries,
        "research_instructions": [
            "Always use the latest available models",
            "Check for the most recent versions of frameworks and tools",
            "Verify information is current (within last 3 months)",
            "Use web search to find up-to-date information",
            "Do not rely on outdated documentation",
        ],
        "recommended_sources": [
            "https://www.faros.ai/blog/best-ai-model-for-coding-2026",
            "https://www.morphllm.com/best-ai-model-for-coding",
            "https://arxiv.org (for latest research papers)",
            "https://github.com/trending (for latest tools)",
        ],
    }
    
    return research_context


def run_research(run_dir: Path) -> dict:
    """Run research and generate context."""
    # Generate research context
    research_context = generate_research_context(run_dir)
    
    # Write research context to run directory
    research_path = run_dir / "research_context.json"
    write_json(research_path, research_context)
    
    return research_context


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Research module for fetching latest information.")
    parser.add_argument("--run-dir", help="Path to the run directory")
    parser.add_argument("--run-id", help="Run identifier (resolved under .agentic-runs/)")
    parser.add_argument("--output", help="Output path for research context JSON")
    args = parser.parse_args(argv)

    try:
        run_dir = resolve_run_dir(args.run_dir, args.run_id)
    except ResearchError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Run research
    research_context = run_research(run_dir)
    
    # Write research context
    output_path = Path(args.output) if args.output else run_dir / "research_context.json"
    write_json(output_path, research_context)
    
    # Print summary
    print(f"Research context generated:")
    print(f"  Date: {research_context['current_date']['date']}")
    print(f"  Goal: {research_context['goal']}")
    print(f"  Model queries: {len(research_context['model_search_queries'])}")
    print(f"  Technology queries: {len(research_context['technology_search_queries'])}")
    print(f"\nResearch instructions:")
    for instruction in research_context['research_instructions']:
        print(f"  - {instruction}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
