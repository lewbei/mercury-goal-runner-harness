#!/usr/bin/env python3
"""Vertical Slice Selector

Reads `macro_plan.json` and `vertical_slice_candidates.json` from the current run directory,
filters, scores and selects the best first vertical slice, writes the result to
`vertical_slice_selection.json`, and prints a short summary.
"""
import json
import os
import sys
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def load_json(path: str) -> Dict[str, Any]:
    """Load a JSON file and return its content as a dict.

    #@ Requires(lambda p: isinstance(p, str) and p, "Path must be a non‑empty string")
    #@ Ensures(lambda result: isinstance(result, dict), "Result must be a dict")
    """
    if not isinstance(path, str) or not path:
        raise TypeError("Path must be a non‑empty string")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root in {path} is not an object")
    return data


def write_json(path: str, content: Dict[str, Any]) -> None:
    """Write `content` to `path` as pretty‑printed JSON.

    #@ Requires(lambda p, c: isinstance(p, str) and p and isinstance(c, dict), "Invalid arguments")
    #@ Ensures(lambda _: True, "File written")
    """
    if not isinstance(path, str) or not path:
        raise TypeError("Path must be a non‑empty string")
    if not isinstance(content, dict):
        raise TypeError("Content must be a dict")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, sort_keys=True)

# ---------------------------------------------------------------------------
# Candidate validation and scoring
# ---------------------------------------------------------------------------

def is_candidate_valid(candidate: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Return (is_valid, reasons). A candidate is valid if it has a `fixture`,
    an `expected_verdict`, and at least three `end_to_end_layers`.

    #@ Requires(lambda c: isinstance(c, dict), "Candidate must be a dict")
    #@ Ensures(lambda r: isinstance(r, tuple) and len(r) == 2, "Returns (bool, list)")
    """
    reasons: List[str] = []
    # fixture check
    if not candidate.get("fixture"):
        reasons.append("Missing fixture")
    # expected_verdict check
    if not candidate.get("expected_verdict"):
        reasons.append("Missing expected_verdict")
    # end_to_end_layers check – assume candidate stores a list under "end_to_end_layers"
    layers = candidate.get("end_to_end_layers")
    if not isinstance(layers, list) or len(layers) < 3:
        reasons.append("Fewer than 3 end_to_end_layers")
    is_valid = len(reasons) == 0
    return is_valid, reasons


def score_candidate(candidate: Dict[str, Any]) -> float:
    """Compute a numeric score for a candidate.

    The score is the sum of the following normalized components:
    - end_to_end_coverage (raw count)
    - fake_done_risk (inverted: 10 - risk)
    - authority_boundary_value (raw)
    - validator_availability (raw)
    - low_implementation_cost (raw, higher is better)
    - replay_certification_impact (raw)

    All raw values are assumed to be integers in the range 1‑10 except
    `end_to_end_coverage` which is a non‑negative integer.

    #@ Requires(lambda c: isinstance(c, dict), "Candidate must be a dict")
    #@ Ensures(lambda s: isinstance(s, (int, float)), "Score must be numeric")
    """
    # Guard against missing keys – default to 0 for coverage and 1 for ratings
    coverage = candidate.get("end_to_end_coverage", 0)
    fake_done_risk = candidate.get("fake_done_risk", 10)  # higher risk => lower contribution
    authority_boundary_value = candidate.get("authority_boundary_value", 1)
    validator_availability = candidate.get("validator_availability", 1)
    low_implementation_cost = candidate.get("low_implementation_cost", 1)
    replay_certification_impact = candidate.get("replay_certification_impact", 1)

    # Normalise the risk (lower is better)
    risk_score = 10 - fake_done_risk

    # Simple weighted sum – all dimensions have weight 1
    total = (
        float(coverage) +
        float(risk_score) +
        float(authority_boundary_value) +
        float(validator_availability) +
        float(low_implementation_cost) +
        float(replay_certification_impact)
    )
    return total

# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for the selector.

    #@ Requires(lambda _: True, "No pre‑conditions")
    #@ Ensures(lambda _: True, "Writes vertical_slice_selection.json and prints summary")
    """
    run_dir = os.path.abspath(os.path.dirname(__file__))
    # The selector lives under .agentic-pi/supervisor, so the run directory is two levels up
    # but the contract says the JSON files are in the run_dir (e.g., .agentic-runs/vslice).
    # We locate the run directory by walking up until we find a directory containing
    # both required files or we reach the repository root.
    # For simplicity we assume the current working directory is the repository root
    # and the run directory is `.agentic-runs/vslice` as given by the environment variable.
    # If the environment variable `RUN_ID` is set we use it.
    run_id = os.getenv("RUN_ID", "vslice")
    run_path = os.path.join(os.getcwd(), ".agentic-runs", run_id)
    macro_path = os.path.join(run_path, "macro_plan.json")
    candidates_path = os.path.join(run_path, "vertical_slice_candidates.json")

    # Load inputs – fail fast if missing
    try:
        macro = load_json(macro_path)
    except Exception as e:
        sys.stderr.write(f"Error loading macro_plan.json: {e}\n")
        sys.exit(1)
    try:
        candidates_data = load_json(candidates_path)
    except Exception as e:
        sys.stderr.write(f"Error loading vertical_slice_candidates.json: {e}\n")
        sys.exit(1)

    # Expect candidates to be a list under the key "candidates"
    candidates: List[Dict[str, Any]] = candidates_data.get("candidates", [])
    if not isinstance(candidates, list):
        sys.stderr.write("Invalid candidates format: expected a list under 'candidates'\n")
        sys.exit(1)

    valid_candidates: List[Tuple[Dict[str, Any], List[str]]] = []
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        is_valid, reasons = is_candidate_valid(cand)
        if is_valid:
            valid_candidates.append((cand, []))
        else:
            # Keep reasons for debugging but do not include in final selection
            valid_candidates.append((cand, reasons))

    # Filter out invalid ones for scoring
    scoring_pool = [cand for cand, reasons in valid_candidates if not reasons]

    if not scoring_pool:
        sys.stderr.write("No valid candidates found after filtering.\n")
        sys.exit(1)

    # Compute scores
    scored: List[Tuple[Dict[str, Any], float]] = []
    for cand in scoring_pool:
        score = score_candidate(cand)
        scored.append((cand, score))

    # Select the best – highest score, tie‑break on end_to_end_coverage
    scored.sort(key=lambda pair: (pair[1], pair[0].get("end_to_end_coverage", 0)), reverse=True)
    best_candidate, best_score = scored[0]

    # Build output structure
    selection = {
        "selected_slice_id": best_candidate.get("slice_id"),
        "score": best_score,
        "reasons": [
            "Candidate passed all validation checks.",
            f"Score breakdown: end_to_end_coverage={best_candidate.get('end_to_end_coverage', 0)}, "
            f"fake_done_risk={best_candidate.get('fake_done_risk', 10)}, "
            f"authority_boundary_value={best_candidate.get('authority_boundary_value', 1)}, "
            f"validator_availability={best_candidate.get('validator_availability', 1)}, "
            f"low_implementation_cost={best_candidate.get('low_implementation_cost', 1)}, "
            f"replay_certification_impact={best_candidate.get('replay_certification_impact', 1)}"
        ]
    }

    # Write selection JSON back to the run directory
    output_path = os.path.join(run_path, "vertical_slice_selection.json")
    try:
        write_json(output_path, selection)
    except Exception as e:
        sys.stderr.write(f"Error writing selection file: {e}\n")
        sys.exit(1)

    # Print a short human‑readable summary (at least two lines)
    print(f"Selected slice: {selection['selected_slice_id']}")
    print(f"Score: {selection['score']:.2f}")

if __name__ == "__main__":
    main()
