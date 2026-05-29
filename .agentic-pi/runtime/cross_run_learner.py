"""cross_run_learner.py

Utility to learn patterns across runs and provide context for new runs.
"""

from __future__ import annotations

import inspect
import json
import sys
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Lightweight runtime contract decorators
# ---------------------------------------------------------------------------

def _call_condition(condition, *args, **kwargs) -> bool:
    """Call a contract condition with only the arguments it declares."""
    try:
        signature = inspect.signature(condition)
    except (TypeError, ValueError):
        return bool(condition(*args, **kwargs))

    params = list(signature.parameters.values())
    if any(p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD) for p in params):
        return bool(condition(*args, **kwargs))

    positional_params = [
        p for p in params
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    keyword_params = [
        p for p in params
        if p.kind in (p.KEYWORD_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    selected_args = args[:len(positional_params)]
    selected_kwargs = {
        p.name: kwargs[p.name]
        for p in keyword_params
        if p.name in kwargs and p.name not in {q.name for q in positional_params[:len(selected_args)]}
    }
    return bool(condition(*selected_args, **selected_kwargs))


def Requires(condition, message=""):
    """Enforce a pre-condition before executing the wrapped function."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not _call_condition(condition, *args, **kwargs):
                raise ValueError(message or f"Pre-condition failed for {func.__name__}")
            return func(*args, **kwargs)
        return wrapper
    return decorator


def Ensures(condition, message=""):
    """Enforce a post-condition after executing the wrapped function."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if not _call_condition(condition, result, *args, **kwargs):
                raise AssertionError(message or f"Post-condition failed for {func.__name__}")
            return result
        return wrapper
    return decorator

# ---------------------------------------------------------------------------
# Core functionality
# ---------------------------------------------------------------------------

@Requires(lambda base_dir=None: isinstance(base_dir, (str, Path)) or base_dir is None, "base_dir must be a string or Path")
@Ensures(lambda result, base_dir=None: isinstance(result, list), "Result must be a list of tuples")
def scan_runs(base_dir: str | Path = ".agentic-runs") -> List[Tuple[str, str]]:
    """Scan all run directories and return a list of (run_id, goal_type).

    The function looks for a `goal_contract.json` file inside each immediate
    sub‑directory of `base_dir`. If the file exists and contains a `goal_type`
    field, the tuple is added to the result list.
    """
    base_path = Path(base_dir)
    runs: List[Tuple[str, str]] = []
    for run_dir in base_path.iterdir():
        if not run_dir.is_dir():
            continue
        goal_contract_path = run_dir / "goal_contract.json"
        if not goal_contract_path.is_file():
            continue
        try:
            with goal_contract_path.open("r", encoding="utf-8") as f:
                contract = json.load(f)
            goal_type = contract.get("goal_type")
            if isinstance(goal_type, str):
                runs.append((run_dir.name, goal_type))
        except Exception:
            # If a contract cannot be parsed we simply skip the run.
            continue
    return runs

@Requires(lambda run_dir: isinstance(run_dir, (str, Path)), "run_dir must be a string or Path")
@Ensures(lambda result, run_dir: isinstance(result, dict), "Result must be a dict of patterns")
def extract_patterns(run_dir: str | Path) -> Dict[str, Any]:
    """Extract simple patterns from a single run.

    Patterns are derived from:
    * `final_status.json` – the top‑level `status` field and any `error` field.
    * `attempt_log.jsonl` – each line is a JSON object; we collect any `error`
      entries.

    The returned dictionary contains a list of `failures` and a list of
    `successes` (if any). The structure is deliberately simple to keep the
    JSON lightweight.
    """
    run_path = Path(run_dir)
    patterns: Dict[str, Any] = {"failures": [], "successes": []}

    # Final status
    final_status_path = run_path / "final_status.json"
    if final_status_path.is_file():
        try:
            with final_status_path.open("r", encoding="utf-8") as f:
                status = json.load(f)
            if status.get("status") == "failed":
                patterns["failures"].append({"source": "final_status", "detail": status.get("error", "unknown error")})
            else:
                patterns["successes"].append({"source": "final_status", "detail": status.get("status")})
        except Exception:
            pass

    # Attempt log (JSON Lines)
    attempt_log_path = run_path / "attempt_log.jsonl"
    if attempt_log_path.is_file():
        try:
            with attempt_log_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if "error" in entry:
                            patterns["failures"].append({"source": "attempt_log", "detail": entry["error"]})
                        else:
                            patterns["successes"].append({"source": "attempt_log", "detail": entry.get("status", "ok")})
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

    return patterns

@Requires(lambda base_dir: isinstance(base_dir, (str, Path)), "base_dir must be a string or Path")
@Ensures(lambda result, base_dir: isinstance(result, dict), "Result must be a dict of grouped patterns")
def load_cross_run_patterns(base_dir: str | Path = ".agentic-pi/runtime") -> Dict[str, List[Dict[str, Any]]]:
    """Load the aggregated patterns JSON file.

    If the file does not exist, an empty dictionary is returned.
    """
    path = Path(base_dir) / "cross_run_patterns.json"
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure the structure is a dict of lists
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if isinstance(v, list)}
    except Exception:
        pass
    return {}

@Requires(lambda patterns: isinstance(patterns, dict), "patterns must be a dict")
@Ensures(lambda patterns, path: True, "No return value")
def save_cross_run_patterns(patterns: Dict[str, List[Dict[str, Any]]], path: str | Path = ".agentic-pi/runtime/cross_run_patterns.json") -> None:
    """Write the aggregated patterns to disk.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        with p.open("w", encoding="utf-8") as f:
            json.dump(patterns, f, indent=2, sort_keys=True)
    except Exception as e:
        print(f"[cross_run_learner] Failed to write patterns: {e}", file=sys.stderr)

@Requires(lambda: True, "always true")
@Ensures(lambda result: isinstance(result, str), "Result must be a string context block")
def pre_run_inject(run_id: str) -> str:
    """Return a context block for the given `run_id`.

    The block lists failure patterns from previous runs that share the same
    `goal_type`. If no patterns exist, a generic message is returned.
    """
    # Determine the goal_type for the requested run
    goal_contract_path = Path(".agentic-runs") / run_id / "goal_contract.json"
    goal_type = None
    if goal_contract_path.is_file():
        try:
            with goal_contract_path.open("r", encoding="utf-8") as f:
                contract = json.load(f)
            goal_type = contract.get("goal_type")
        except Exception:
            pass

    if not goal_type:
        return f"[cross_run_learner] No goal_type found for run_id '{run_id}'."

    patterns_by_type = load_cross_run_patterns()
    patterns = patterns_by_type.get(goal_type, [])
    if not patterns:
        return f"[cross_run_learner] No prior patterns for goal_type '{goal_type}'."

    # Build a simple readable block
    lines = [f"[cross_run_learner] Similar runs for goal_type '{goal_type}':"]
    for i, pat in enumerate(patterns[:5], start=1):
        source = pat.get("source", "unknown")
        detail = pat.get("detail", "")
        lines.append(f"  {i}. [{source}] {detail}")
    return "\n".join(lines)

@Requires(lambda: True, "always true")
@Ensures(lambda: True, "no return")
def update_cross_run_patterns() -> None:
    """Scan all runs, extract patterns, and store them grouped by goal_type.
    """
    runs = scan_runs()
    aggregated: Dict[str, List[Dict[str, Any]]] = {}
    for run_id, goal_type in runs:
        run_dir = Path(".agentic-runs") / run_id
        patterns = extract_patterns(run_dir)
        # Flatten failures and successes into a single list for simplicity
        for entry in patterns.get("failures", []):
            aggregated.setdefault(goal_type, []).append(entry)
        for entry in patterns.get("successes", []):
            aggregated.setdefault(goal_type, []).append(entry)
    save_cross_run_patterns(aggregated)

# ---------------------------------------------------------------------------
# Entry point for manual execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Update the global pattern store
    update_cross_run_patterns()
    print("[cross_run_learner] Cross-run patterns have been updated.")
    # Demonstrate injection for a sample run (use first argument if provided)
    sample_run = sys.argv[1] if len(sys.argv) > 1 else "xrun"
    context = pre_run_inject(sample_run)
    print(context)
