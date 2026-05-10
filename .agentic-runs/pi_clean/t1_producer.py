# t1_producer.py
"""
Produces the initial artifact for the dependency proof.

The script writes a JSON file containing a fixed artifact ID "A.SOURCE"
and optional payload data. The file is stored under the "artifacts"
directory as "t1_artifact.json".
"""

import json
from pathlib import Path


def main() -> None:
    """Create the artifact file with the required ID."""
    artifact_dir = Path(__file__).parent / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = artifact_dir / "t1_artifact.json"
    artifact_data = {
        "artifact_id": "A.SOURCE",
        "payload": "Data produced by T1"
    }

    try:
        artifact_path.write_text(json.dumps(artifact_data, indent=2))
    except OSError as exc:
        raise RuntimeError(f"Failed to write artifact: {exc}") from exc


if __name__ == "__main__":
    main()
