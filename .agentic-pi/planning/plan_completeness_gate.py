#!/usr/bin/env python
"""Plan Completeness Gate.

Validates the current run-local planning coverage artifact and writes a
`plan_completeness_report.json` file. The current strict artifact is
`planning_coverage.json`; the older `plan_coverage_matrix.json` format remains
accepted only as a legacy fallback.
"""

import json
import os
import sys
from dataclasses import dataclass
from typing import List, Dict

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class PlanCompletenessError(Exception):
    """Base class for all plan‑completeness‑gate errors."""

class ValidationError(PlanCompletenessError):
    """Raised when a validation rule fails."""

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class Dimension:
    name: str
    covered: bool
    task: str
    artifact: str
    validator: str
    verifier: str
    authority: str
    status: str

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def load_json(path: str) -> Dict:
    """Load a JSON file, raising a clear error if the file does not exist.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed JSON object.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Required file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_dimensions(dimensions: List[Dict]) -> List[str]:
    """Validate each dimension entry.

    Returns a list of gap messages; an empty list means no gaps.
    """
    gaps: List[str] = []
    for dim in dimensions:
        name = dim.get("name", "<unknown>")
        # 2. Artifact path must be a non‑empty string
        if not isinstance(dim.get("artifact"), str) or not dim["artifact"]:
            gaps.append(f"Artifact missing for dimension {name}")
        # 3. Task must be a non‑empty string
        if not isinstance(dim.get("task"), str) or not dim["task"]:
            gaps.append(f"Task missing for dimension {name}")
        # 4. Validator must be present
        if not isinstance(dim.get("validator"), str) or not dim["validator"]:
            gaps.append(f"Validator missing for dimension {name}")
        # 5. Authority must be one of the allowed levels
        if dim.get("authority") not in {"P0", "P1", "P2", "P3"}:
            gaps.append(f"Invalid authority {dim.get('authority')} for dimension {name}")
        # 6. No placeholder strings in any textual field
        for field in ["task", "artifact", "validator", "verifier", "status"]:
            value = dim.get(field, "")
            if isinstance(value, str) and any(p in value.lower() for p in ["todo", "unknown", "later", "agent decides"]):
                gaps.append(f"Placeholder found in {field} of dimension {name}")
        # 7. No blocking unknowns (status == UNRESOLVED and blocking == true)
        if dim.get("status") == "UNRESOLVED" and dim.get("blocking", False):
            gaps.append(f"Blocking unknown in dimension {name}")
    return gaps


def validate_success_criteria(criteria: List[Dict]) -> List[str]:
    """Validate that each success criterion has a validator and no placeholders.
    """
    gaps: List[str] = []
    for crit in criteria:
        criterion = crit.get("criterion", "<unknown>")
        if not isinstance(crit.get("validator"), str) or not crit["validator"]:
            gaps.append(f"Validator missing for success criterion '{criterion}'")
        if any(p in criterion.lower() for p in ["todo", "unknown", "later", "agent decides"]):
            gaps.append(f"Placeholder in success criterion '{criterion}'")
    return gaps


def compute_score(dimensions: List[Dict]) -> float:
    """Return a completeness score in the range 0.0‑1.0.
    """
    total = len(dimensions)
    if total == 0:
        return 0.0
    covered = sum(1 for d in dimensions if d.get("covered"))
    return covered / total


def validate_planning_coverage(data: Dict) -> List[str]:
    """Validate the current planning_coverage.json gate semantics.

    This is intentionally a planning gate, not certification. The stronger
    schema/semantic validator still lives in
    `.agentic-pi/validators/validate_planning_coverage.py`; this gate only
    checks that the run cannot leave planning with missing, failing, or
    authority-claiming coverage.
    """
    gaps: List[str] = []
    if data.get("schema_version") != "planning_coverage_v1":
        gaps.append("planning_coverage.json schema_version must be planning_coverage_v1")

    authority = data.get("authority", {})
    if authority.get("can_certify_done") is not False:
        gaps.append("planning coverage must not certify DONE")
    if authority.get("claim_exhaustive_planning") is not False:
        gaps.append("planning coverage must not claim exhaustive planning")
    if authority.get("claim_correctness") is not False:
        gaps.append("planning coverage must not claim correctness")
    if authority.get("final_status_authority") != "certifier_only":
        gaps.append("planning coverage final status authority must be certifier_only")

    proof_boundary = data.get("proof_boundary", {})
    if proof_boundary.get("proves_all_possible_plans") is not False:
        gaps.append("planning coverage must not prove all possible plans")
    if proof_boundary.get("proves_artifact_correctness") is not False:
        gaps.append("planning coverage must not prove artifact correctness")
    for required_gate in ["requires_worker_execution", "requires_verifier_artifacts", "requires_policy_engine", "requires_certifier"]:
        if proof_boundary.get(required_gate) is not True:
            gaps.append(f"planning coverage proof boundary must require {required_gate}")

    search_budget = data.get("search_budget", {})
    if search_budget.get("search_completeness_claim") != "bounded_not_exhaustive":
        gaps.append("planning coverage must claim bounded_not_exhaustive search")

    alternatives = data.get("alternatives_considered", [])
    if not alternatives:
        gaps.append("planning coverage must record alternatives_considered")
    elif not any(item.get("status") == "selected" for item in alternatives if isinstance(item, dict)):
        gaps.append("planning coverage must record one selected alternative")

    checks = data.get("coverage_checks", [])
    if not checks:
        gaps.append("planning coverage must record coverage_checks")
    failing = [item.get("check_id", "<unknown>") for item in checks if isinstance(item, dict) and item.get("status") == "FAIL"]
    if failing:
        gaps.append(f"planning coverage checks failed: {', '.join(failing[:5])}")

    verification = data.get("verification_strategy", {})
    if not verification.get("verifier_requirements"):
        gaps.append("planning coverage must record verifier requirements")
    boundary = verification.get("policy_boundary", "")
    if "policy_engine.py" not in boundary and "certify_run.py" not in boundary:
        gaps.append("planning coverage must hand off to policy_engine.py or certify_run.py")

    return gaps


# ---------------------------------------------------------------------------
# Main routine
# ---------------------------------------------------------------------------

def main(argv: list = None) -> None:
    if argv is None:
        argv = sys.argv
    # Accept run_dir as command-line argument, or default
    if len(argv) >= 2:
        base_dir = os.path.abspath(argv[1])
    else:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".agentic-runs", "plangate"))
    coverage_path = os.path.join(base_dir, "planning_coverage.json")
    legacy_coverage_path = os.path.join(base_dir, "plan_coverage_matrix.json")
    report_path = os.path.join(base_dir, "plan_completeness_report.json")

    if os.path.exists(coverage_path):
        data = load_json(coverage_path)
        gaps = validate_planning_coverage(data)
        plan_complete = not gaps
        report = {
            "plan_complete": plan_complete,
            "score": 1.0 if plan_complete else 0.0,
            "gaps": gaps,
            "covered_dimensions": len(data.get("coverage_checks", [])),
            "source_artifact": "planning_coverage.json",
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Plan completeness report written to {report_path}")
        return

    # Legacy fallback for pre-strict fixtures.
    coverage_path = legacy_coverage_path

    # Load the legacy coverage matrix
    data = load_json(coverage_path)
    dimensions = data.get("dimensions", [])
    success_criteria = data.get("success_criteria", [])

    # Perform validations
    gaps: List[str] = []
    gaps.extend(validate_dimensions(dimensions))
    gaps.extend(validate_success_criteria(success_criteria))

    # 8. Final status gate mapping – not represented in the matrix; assume present.
    # 9. Phase coverage – ensure all required phases exist.
    required_phases = {"Question", "Research", "Design", "Structure", "PlanGraph", "Implement", "Verify", "Policy", "Replay", "Certify", "Report", "Memory"}
    present_phases = {d.get("name") for d in dimensions}
    missing_phases = required_phases - present_phases
    if missing_phases:
        gaps.append(f"Missing phases: {', '.join(sorted(missing_phases))}")

    # Compute completeness score
    score = compute_score(dimensions)
    plan_complete = score == 1.0 and not gaps

    # Write the report
    report = {
        "plan_complete": plan_complete,
        "score": round(score, 2),
        "gaps": gaps,
        "covered_dimensions": len(dimensions),
        "source_artifact": "plan_coverage_matrix.json"
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Plan completeness report written to {report_path}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Wrap any unexpected error in ValidationError for a clean exit code.
        raise ValidationError(f"Plan completeness validation failed: {exc}") from exc
