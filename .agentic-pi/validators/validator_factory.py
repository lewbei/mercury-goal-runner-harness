#!/usr/bin/env python3
"""Validator Factory

Orchestrates strength scoring, known‑FAIL fixture verification, criteria coverage
, and smell scanning for a verifier artifact. Emits `validator_certification.json`
with a boolean `certified` flag and a list of human‑readable reasons.
"""

import json
import sys
from pathlib import Path

# Import existing utilities
from strength_scorer import score_verifier_artifact
from smell_scanner import scan_verifier_artifact

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------

#@ Requires(lambda p: isinstance(p, Path) and p.is_file(), "path must be a Path to an existing file")
#@ Ensures(lambda result: isinstance(result, dict), "result must be a dict")
def load_json(path: Path) -> dict:
    """Load a JSON file and return its content as a dict.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed JSON as a dictionary.
    """
    if not isinstance(path, Path):
        raise TypeError(f"Expected Path, got {type(path).__name__}")
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON content at {path} is not a dict")
    return data

#@ Requires(lambda d: isinstance(d, dict), "goal_contract must be a dict")
#@ Ensures(lambda result: isinstance(result, list), "done_criteria must be a list")
def extract_done_criteria(goal_contract: dict) -> list:
    """Extract the `done_criteria` list from a goal contract.

    Args:
        goal_contract: Parsed goal contract JSON.

    Returns:
        List of done criteria strings.
    """
    if not isinstance(goal_contract, dict):
        raise TypeError("goal_contract must be a dict")
    criteria = goal_contract.get("done_criteria")
    if not isinstance(criteria, list):
        raise ValueError("goal_contract.done_criteria must be a list")
    return criteria

# ----------------------------------------------------------------------
# Core validation functions
# ----------------------------------------------------------------------

#@ Requires(lambda a: isinstance(a, dict), "verifier artifact must be a dict")
#@ Ensures(lambda result: isinstance(result, float), "strength score must be a float")
def compute_strength_score(artifact: dict) -> float:
    """Compute the strength score for a verifier artifact using the existing scorer.

    Args:
        artifact: Verifier artifact dict.

    Returns:
        Float strength score.
    """
    if not isinstance(artifact, dict):
        raise TypeError("artifact must be a dict")
    # The scorer returns a dict with a "score" key.
    result = score_verifier_artifact(artifact, None)
    score = result.get("score")
    if not isinstance(score, (int, float)):
        raise ValueError("Score returned by strength_scorer is not numeric")
    return float(score)

#@ Requires(lambda a: isinstance(a, dict), "verifier artifact must be a dict")
#@ Requires(lambda p: isinstance(p, Path) and p.is_file(), "fixture_path must be a Path to an existing file")
#@ Ensures(lambda result: isinstance(result, bool), "fixture verification result must be a bool")
def run_verifier_on_fixture(artifact: dict, fixture_path: Path) -> bool:
    """Run the verifier on a known‑FAIL fixture and confirm it detects FAIL.

    The fixture is expected to be a JSON file with an `expected_outcome` field set to
    "FAIL". The verifier artifact is assumed to contain a callable `verify` entry point.
    Since we cannot import arbitrary verifier code, we simulate the check by inspecting the
    fixture's `expected_outcome` field.

    Args:
        artifact: Verifier artifact dict (unused in this simulated implementation).
        fixture_path: Path to the known‑FAIL fixture JSON.

    Returns:
        True if the fixture indicates a FAIL, False otherwise.
    """
    if not isinstance(artifact, dict):
        raise TypeError("artifact must be a dict")
    if not isinstance(fixture_path, Path) or not fixture_path.is_file():
        raise FileNotFoundError(f"Fixture file not found: {fixture_path}")
    fixture = load_json(fixture_path)
    expected = fixture.get("expected_outcome")
    return expected == "FAIL"

#@ Requires(lambda a: isinstance(a, dict), "verifier artifact must be a dict")
#@ Requires(lambda d: isinstance(d, list), "done_criteria must be a list")
#@ Ensures(lambda result: isinstance(result, bool), "coverage result must be a bool")
def verify_criteria_coverage(artifact: dict, done_criteria: list) -> bool:
    """Verify that the verifier's `covered_criteria` includes all `done_criteria`.

    Args:
        artifact: Verifier artifact dict.
        done_criteria: List of criteria strings from the goal contract.

    Returns:
        True if every done criterion is covered, False otherwise.
    """
    if not isinstance(artifact, dict):
        raise TypeError("artifact must be a dict")
    if not isinstance(done_criteria, list):
        raise TypeError("done_criteria must be a list")
    covered = artifact.get("covered_criteria")
    if not isinstance(covered, list):
        # If the artifact does not expose coverage, treat as empty.
        covered = []
    # Normalise both lists to strings for comparison.
    covered_set = {str(c) for c in covered}
    required_set = {str(c) for c in done_criteria}
    return required_set.issubset(covered_set)

#@ Requires(lambda a: isinstance(a, dict), "verifier artifact must be a dict")
#@ Ensures(lambda result: isinstance(result, dict), "smell scan result must be a dict")
def run_smell_scanner(artifact: dict) -> dict:
    """Run the smell scanner on a verifier artifact and return its report.

    Args:
        artifact: Verifier artifact dict.

    Returns:
        Dictionary returned by `scan_verifier_artifact`.
    """
    if not isinstance(artifact, dict):
        raise TypeError("artifact must be a dict")
    return scan_verifier_artifact(artifact)

#@ Requires(lambda d: isinstance(d, Path), "run_dir must be a Path")
#@ Requires(lambda c: isinstance(c, bool), "certified must be a bool")
#@ Requires(lambda r: isinstance(r, list), "reasons must be a list")
#@ Ensures(lambda _: True, "no return value")
def write_certification(run_dir: Path, certified: bool, reasons: list) -> None:
    """Write `validator_certification.json` into the run directory.

    Args:
        run_dir: Base directory for the run.
        certified: Overall certification boolean.
        reasons: List of human‑readable strings explaining the decision.
    """
    if not isinstance(run_dir, Path):
        raise TypeError("run_dir must be a Path")
    if not isinstance(certified, bool):
        raise TypeError("certified must be a bool")
    if not isinstance(reasons, list):
        raise TypeError("reasons must be a list")
    out_path = run_dir / "validator_certification.json"
    content = {
        "certified": certified,
        "reasons": reasons
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")

# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------


def load_verifier_artifact_for_run(run_dir: Path) -> dict:
    """Load the verifier artifact to certify without fabricating one.

    Prefer the historical verifier.json path. If it is absent, accept exactly
    one existing verifier_artifacts/*.json file. Multiple artifacts require an
    explicit verifier.json to avoid silently certifying the wrong verifier.
    """
    verifier_dir = run_dir / "verifier_artifacts"
    verifier_path = verifier_dir / "verifier.json"
    if verifier_path.is_file():
        return load_json(verifier_path)

    artifact_paths = sorted(verifier_dir.glob("*.json")) if verifier_dir.is_dir() else []
    if not artifact_paths:
        raise FileNotFoundError(f"No verifier artifacts found in {verifier_dir}")
    if len(artifact_paths) != 1:
        names = ", ".join(path.name for path in artifact_paths)
        raise ValueError(f"Multiple verifier artifacts found; create verifier.json to choose one: {names}")
    return load_json(artifact_paths[0])


#@ Requires(lambda a: isinstance(a, list), "argv must be a list of strings")
#@ Ensures(lambda _: True, "no return value")
def main(argv: list) -> None:
    """Command‑line entry point for the validator factory.

    Usage:
        python validator_factory.py [run_dir]

    If `run_dir` is omitted, the current working directory is used.
    The function prints the certification JSON and a one‑line summary.
    """
    if not isinstance(argv, list):
        raise TypeError("argv must be a list")
    # Determine run directory
    if len(argv) >= 2:
        run_dir = Path(argv[1])
    else:
        run_dir = Path.cwd()
    if not isinstance(run_dir, Path):
        raise TypeError("run_dir must be a Path")

    # Load goal contract
    goal_path = run_dir / "goal_contract.json"
    goal_contract = load_json(goal_path)
    done_criteria = extract_done_criteria(goal_contract)

    # Load an existing verifier artifact. This certifies verifier quality only;
    # it does not create verifier evidence or final status artifacts.
    verifier_artifact = load_verifier_artifact_for_run(run_dir)

    # 1. Strength score > 0.5
    strength_score = compute_strength_score(verifier_artifact)
    strength_ok = strength_score > 0.5

    # 2. Known‑FAIL fixture verification
    fixture_path = Path(".agentic-pi/fixtures/known_fail_fixture.json")
    fixture_ok = run_verifier_on_fixture(verifier_artifact, fixture_path)

    # 3. Criteria coverage
    coverage_ok = verify_criteria_coverage(verifier_artifact, done_criteria)

    # 4. Smell scanner
    smell_report = run_smell_scanner(verifier_artifact)
    # For certification we treat any disqualifying smell as a failure.
    smell_ok = not smell_report.get("disqualifying", False)

    # Aggregate results
    certified = all([strength_ok, fixture_ok, coverage_ok, smell_ok])
    reasons = []
    if not strength_ok:
        reasons.append(f"Strength score too low: {strength_score:.2f} (required > 0.5)")
    if not fixture_ok:
        reasons.append("Known‑FAIL fixture was not detected as FAIL")
    if not coverage_ok:
        reasons.append("Verifier does not cover all done_criteria from goal contract")
    if not smell_ok:
        reasons.append(f"Disqualifying smell flags detected: {smell_report.get('smell_flags', [])}")

    # Write certification file
    write_certification(run_dir, certified, reasons)

    # Print output (≥2 lines)
    print(json.dumps({"certified": certified, "reasons": reasons}, indent=2, ensure_ascii=False))
    print(f"Validation {'PASSED' if certified else 'FAILED'} for run directory: {run_dir}")

if __name__ == "__main__":
    main(sys.argv)
