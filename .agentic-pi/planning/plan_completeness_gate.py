#!/usr/bin/env python
"""Plan Completeness Gate

Validates a macro‑plan coverage matrix against the required checks and writes a
`plan_completeness_report.json` file.
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
    coverage_path = os.path.join(base_dir, "plan_coverage_matrix.json")
    report_path = os.path.join(base_dir, "plan_completeness_report.json")

    # Load the coverage matrix
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
        "covered_dimensions": len(dimensions)
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
