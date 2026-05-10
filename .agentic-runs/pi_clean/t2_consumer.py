# t2_consumer.py
"""
Consumes the artifact produced by T1 and verifies the artifact ID.

The script reads "artifacts/t1_artifact.json", checks that the
"artifact_id" field exactly matches "A.SOURCE", and writes a marker
file "artifacts/t2_success.txt" on success.
"""

import json
from pathlib import Path

EXPECTED_ID = "A.SOURCE"


def load_artifact(path: Path) -> dict:
    """Load JSON artifact from the given path."""
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Failed to read or parse artifact: {exc}") from exc


def validate_artifact(artifact: dict) -> None:
    """Validate that the artifact contains the expected ID."""
    artifact_id = artifact.get("artifact_id")
    if artifact_id != EXPECTED_ID:
        raise ValueError(f"Unexpected artifact_id: {artifact_id!r}. Expected {EXPECTED_ID!r}")


def write_success_marker(dir_path: Path) -> None:
    """Write a simple marker file indicating successful consumption."""
    marker_path = dir_path / "t2_success.txt"
    try:
        marker_path.write_text("T2 consumed artifact successfully.\n")
    except OSError as exc:
        raise RuntimeError(f"Failed to write success marker: {exc}") from exc


def main() -> None:
    """Main entry point for T2."""
    artifact_dir = Path(__file__).parent / "artifacts"
    artifact_path = artifact_dir / "t1_artifact.json"

    artifact = load_artifact(artifact_path)
    validate_artifact(artifact)
    write_success_marker(artifact_dir)


if __name__ == "__main__":
    main()
