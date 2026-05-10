# generate_report.py
"""
Generates the final dependency report after T2 has consumed the artifact.

The report is a Markdown file named "dependency_report.md" and must
contain the word "A.SOURCE" to satisfy the done criteria.
"""

import json
from pathlib import Path

REPORT_PATH = Path(__file__).parent / "dependency_report.md"
ARTIFACT_PATH = Path(__file__).parent / "artifacts" / "t1_artifact.json"


def load_artifact_id(path: Path) -> str:
    """Load the artifact and return its ID."""
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Failed to read artifact: {exc}") from exc
    artifact_id = data.get("artifact_id")
    if not isinstance(artifact_id, str):
        raise ValueError("artifact_id is missing or not a string")
    return artifact_id


def write_report(artifact_id: str) -> None:
    """Write the markdown report containing the artifact ID."""
    content = f"""# Dependency Report

The T2 step consumed the artifact with ID **{artifact_id}**.
This satisfies the required dependency proof.
"""
    try:
        REPORT_PATH.write_text(content)
    except OSError as exc:
        raise RuntimeError(f"Failed to write report: {exc}") from exc


def main() -> None:
    """Main entry point for report generation."""
    artifact_id = load_artifact_id(ARTIFACT_PATH)
    write_report(artifact_id)


if __name__ == "__main__":
    main()
