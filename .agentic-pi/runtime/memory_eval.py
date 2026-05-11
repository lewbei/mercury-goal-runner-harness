# .agentic-pi/runtime/memory_eval.py
"""Memory Evaluation Benchmark

Simulates a series of goals with and without memory injection, tracks success rates,
records injection quality, writes learning cards, and produces a final JSON report.
"""

import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, Dict, Any

# ---------------------------------------------------------------------------
# Local imports – smart_memory provides the context builder and quality recorder
# ---------------------------------------------------------------------------
try:
    from smart_memory import build_context_block, record_injection_quality
except Exception as exc:
    raise ImportError(f"Failed to import smart_memory helpers: {exc}") from exc

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class EvaluationError(RuntimeError):
    """Raised for unrecoverable errors during the benchmark execution."""

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class Goal:
    """Simple representation of a simulated goal.

    Attributes
    ----------
    goal_id: str
        Unique identifier for the goal.
    description: str
        Human‑readable description.
    goal_type: str
        One of "string", "sorting", "mixed" – used only for grouping.
    success_patterns: List[str]
        Regular‑expression patterns that, when found in the injected context, indicate a successful run.
    """
    goal_id: str
    description: str
    goal_type: str
    success_patterns: List[str]

@dataclass
class RunResult:
    """Result of a single mock‑agent run.

    Attributes
    ----------
    success: bool
        Whether the goal was considered satisfied.
    used_card_ids: List[str]
        IDs of memory cards that contributed to the context block.
    injection_quality: float
        Score recorded by `smart_memory.record_injection_quality` (0‑1).
    """
    success: bool
    used_card_ids: List[str]
    injection_quality: float

# ---------------------------------------------------------------------------
# Goal catalogue – 10+ goals grouped by similarity
# ---------------------------------------------------------------------------
GOALS: List[Goal] = [
    # 1‑3: String operations
    Goal(
        goal_id="G001",
        description="Reverse a string and check if it equals its original (palindrome test).",
        goal_type="string",
        success_patterns=[r"palindrome", r"reverse", r"string"]
    ),
    Goal(
        goal_id="G002",
        description="Concatenate three substrings and verify length.",
        goal_type="string",
        success_patterns=[r"concatenat", r"substring", r"length"]
    ),
    Goal(
        goal_id="G003",
        description="Replace all vowels in a string with '*'.",
        goal_type="string",
        success_patterns=[r"vowel", r"replace", r"asterisk"]
    ),
    # 4‑6: Sorting tasks
    Goal(
        goal_id="G004",
        description="Sort a list of integers in ascending order.",
        goal_type="sorting",
        success_patterns=[r"sort", r"ascending", r"integer"]
    ),
    Goal(
        goal_id="G005",
        description="Sort a list of strings alphabetically, case‑insensitive.",
        goal_type="sorting",
        success_patterns=[r"alphabetic", r"case‑insensitive", r"sort"]
    ),
    Goal(
        goal_id="G006",
        description="Stable sort a list of tuples by the second element.",
        goal_type="sorting",
        success_patterns=[r"stable", r"tuple", r"second element"]
    ),
    # 7‑10: Mixed operations
    Goal(
        goal_id="G007",
        description="Find the most frequent word in a text after stripping punctuation.",
        goal_type="mixed",
        success_patterns=[r"most frequent", r"word", r"punctuation"]
    ),
    Goal(
        goal_id="G008",
        description="Compute the Levenshtein distance between two strings.",
        goal_type="mixed",
        success_patterns=[r"levenshtein", r"distance", r"string"]
    ),
    Goal(
        goal_id="G009",
        description="Parse a CSV line into fields and sum numeric columns.",
        goal_type="mixed",
        success_patterns=[r"csv", r"parse", r"sum"]
    ),
    Goal(
        goal_id="G010",
        description="Detect if a list contains a duplicate element.",
        goal_type="mixed",
        success_patterns=[r"duplicate", r"list", r"detect"]
    ),
]

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def extract_card_ids_from_context(context: str) -> List[str]:
    """Extract card IDs embedded in the context block.

    The smart_memory pipeline does not embed IDs by default; for the purpose of the
    benchmark we look for a simple marker ``CARD_ID:<id>`` that can be added by the
    mock agent when it records which cards contributed.
    """
    pattern = re.compile(r"CARD_ID:([A-Za-z0-9_-]+)")
    return pattern.findall(context)


def run_mock_agent(goal: Goal, context: str) -> RunResult:
    """Deterministic mock of an LLM agent.

    The mock succeeds if *any* of ``goal.success_patterns`` matches the injected
    ``context`` (case‑insensitive). It also extracts any ``CARD_ID`` markers from the
    context to simulate which memory cards were used.

    Parameters
    ----------
    goal: Goal
        The simulated goal.
    context: str
        Memory context block (may be empty).

    Returns
    -------
    RunResult
        Success flag, list of used card IDs, and a dummy injection quality score.
    """
    # Normalise context for regex matching
    lowered = context.lower()
    success = any(re.search(pat.lower(), lowered) for pat in goal.success_patterns)
    used_ids = extract_card_ids_from_context(context)
    # Dummy quality: proportion of matched patterns (0‑1)
    matched = sum(1 for pat in goal.success_patterns if re.search(pat.lower(), lowered))
    quality = matched / len(goal.success_patterns) if goal.success_patterns else 0.0
    return RunResult(success=success, used_card_ids=used_ids, injection_quality=quality)


def write_learning_card(batch_idx: int, goals: List[Goal], results: List[RunResult]) -> None:
    """Persist a learning card for a batch of goals.

    The card records the union of all success patterns that were *matched* in the
    assisted runs of the batch, the overall outcome (success count), and a timestamp.
    The file is stored under ``memory/durable/learning_cards/`` with a name like
    ``batch_01.json``.
    """
    card_dir = Path(__file__).resolve().parents[2] / "memory" / "durable" / "learning_cards"
    card_dir.mkdir(parents=True, exist_ok=True)
    matched_patterns: List[str] = []
    success_count = 0
    for goal, res in zip(goals, results):
        if res.success:
            success_count += 1
            matched_patterns.extend(goal.success_patterns)
    # Deduplicate patterns and keep a short list
    matched_patterns = list(dict.fromkeys(matched_patterns))[:10]
    card_content = {
        "batch_index": batch_idx,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "goals": [g.goal_id for g in goals],
        "matched_patterns": matched_patterns,
        "success_count": success_count,
        "total_goals": len(goals),
    }
    card_path = card_dir / f"batch_{batch_idx:02d}.json"
    try:
        card_path.write_text(json.dumps(card_content, indent=2, ensure_ascii=False), encoding="utf-8")
        logging.info("Wrote learning card %s", card_path)
    except Exception as exc:
        raise EvaluationError(f"Failed to write learning card {card_path}: {exc}") from exc


def write_report(
    baseline_success: float,
    assisted_success: float,
    quality_trend: List[float],
    decay_impact: float,
) -> None:
    """Write the final evaluation report to ``eval_report.json``.

    The report contains:
    - baseline_success_rate
    - assisted_success_rate
    - improvement (percentage points)
    - quality_trend (list of injection quality scores per batch)
    - decay_impact (difference between early and late quality scores)
    """
    report = {
        "baseline_success_rate": baseline_success,
        "assisted_success_rate": assisted_success,
        "improvement": assisted_success - baseline_success,
        "quality_trend": quality_trend,
        "decay_impact": decay_impact,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    out_path = Path(__file__).resolve().parent / "eval_report.json"
    try:
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        logging.info("Evaluation report written to %s", out_path)
    except Exception as exc:
        raise EvaluationError(f"Failed to write eval_report.json: {exc}") from exc

# ---------------------------------------------------------------------------
# Main simulation logic
# ---------------------------------------------------------------------------

def main(token_budget: int = 2000) -> None:
    """Run the full benchmark.

    Parameters
    ----------
    token_budget: int, optional
        Maximum number of characters for the memory context block.
    """
    baseline_results: List[RunResult] = []
    assisted_results: List[RunResult] = []
    quality_trend: List[float] = []
    batch_size = 3  # aligns with similarity groups
    total_batches = (len(GOALS) + batch_size - 1) // batch_size

    for batch_idx in range(total_batches):
        batch_start = batch_idx * batch_size
        batch_goals = GOALS[batch_start : batch_start + batch_size]

        # Baseline runs – no memory injection
        for goal in batch_goals:
            result = run_mock_agent(goal, context="")
            baseline_results.append(result)

        # Assisted runs – inject memory context per goal
        assisted_batch_results: List[RunResult] = []
        for goal in batch_goals:
            # Build context using smart_memory; the function internally loads durable cards
            context = build_context_block(run_id=goal.goal_id, token_budget=token_budget)
            # Record injection quality via the helper (it writes a JSON file per call)
            # The helper expects a boolean success flag; we compute it after the mock run
            mock_res = run_mock_agent(goal, context=context)
            # The helper writes the JSON; we also keep the quality score locally
            record_injection_quality(run_id=goal.goal_id, success=mock_res.success, used_card_ids=mock_res.used_card_ids)
            assisted_batch_results.append(mock_res)
            quality_trend.append(mock_res.injection_quality)

        # Write a learning card for the batch (using assisted results)
        write_learning_card(batch_idx=batch_idx + 1, goals=batch_goals, results=assisted_batch_results)
        assisted_results.extend(assisted_batch_results)

    # Aggregate statistics
    baseline_success_rate = sum(r.success for r in baseline_results) / len(baseline_results) if baseline_results else 0.0
    assisted_success_rate = sum(r.success for r in assisted_results) / len(assisted_results) if assisted_results else 0.0
    # Decay impact – compare first half vs second half of quality trend
    half = len(quality_trend) // 2
    early_avg = sum(quality_trend[:half]) / half if half > 0 else 0.0
    late_avg = sum(quality_trend[half:]) / (len(quality_trend) - half) if len(quality_trend) - half > 0 else 0.0
    decay_impact = early_avg - late_avg

    # Write final report
    write_report(
        baseline_success=baseline_success_rate,
        assisted_success=assisted_success_rate,
        quality_trend=quality_trend,
        decay_impact=decay_impact,
    )

    # Summary output for the user
    logging.info("Baseline success rate: %.2f%%", baseline_success_rate * 100)
    logging.info("Assisted success rate: %.2f%%", assisted_success_rate * 100)
    logging.info("Improvement: %.2f%%", (assisted_success_rate - baseline_success_rate) * 100)
    logging.info("Injection quality trend (per run): %s", quality_trend)
    logging.info("Decay impact (early - late): %.4f", decay_impact)

if __name__ == "__main__":
    # Simple CLI – optional token budget argument
    import argparse
    parser = argparse.ArgumentParser(description="Run the memory evaluation benchmark")
    parser.add_argument("--budget", type=int, default=2000, help="Token budget for memory context (characters)")
    args = parser.parse_args()
    try:
        main(token_budget=args.budget)
    except EvaluationError as ee:
        logging.error("Benchmark failed: %s", ee)
        sys.exit(1)
    except Exception as exc:
        logging.exception("Unexpected error during benchmark")
        sys.exit(1)
