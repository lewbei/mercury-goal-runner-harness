# Thinking Plan: Create a two-step artifact dependency proof for the harness

## Architecture

We will implement the dependency proof using three small, single‑purpose Python scripts stored at the repository root:

- **t1_producer.py** – Generates the initial artifact (`artifacts/t1_artifact.json`) containing the fixed ID `A.SOURCE`.
- **t2_consumer.py** – Reads the artifact, validates that the `artifact_id` exactly matches `A.SOURCE`, and writes a success marker (`artifacts/t2_success.txt`).
- **generate_report.py** – After T2 succeeds, reads the same artifact and writes `dependency_report.md` that includes the word `A.SOURCE` (required by the done criteria).

All artifacts live under an `artifacts/` directory created on‑demand. Using JSON for the artifact gives a clear schema and easy extensibility while keeping the implementation dependency‑free (standard library only). The three‑step separation makes the dependency explicit and mirrors the "two‑step artifact dependency proof" described in the goal.

## Design decisions

| Decision | Alternatives considered | Chosen approach | Rationale |
|----------|--------------------------|----------------|-----------|
| **Artifact format** | Plain text, CSV, JSON | JSON | JSON provides a self‑describing key (`artifact_id`) and scales if more fields are needed later. |
| **ID propagation** | Environment variable, file, command‑line argument | File (`artifacts/t1_artifact.json`) | Files are persistent across separate script executions and avoid shell‑specific handling. |
| **Separate report generation** | Combine T2 and report in one script, separate script | Separate `generate_report.py` | Keeps each script focused, simplifies validation, and mirrors the "after T2 consumes" requirement. |
| **CLI vs direct execution** | `argparse` interface, simple `main()` | Simple `main()` with no arguments | The scripts are invoked directly by the implementer; no parameters are needed for this proof of concept. |
| **Error handling** | Silent failures, logging, explicit exceptions | Explicit `raise` with clear messages | Guarantees that any deviation (e.g., wrong ID) aborts the pipeline, making debugging straightforward. |

---

## Step 1: t1_producer.py

### Why
T1 is the source of the artifact. It must run first to create the JSON file that T2 and the report will later consume. Establishing the artifact early also ensures the directory structure (`artifacts/`) exists for downstream steps.

### Design
- Create `artifacts/` if it does not exist.
- Write a JSON file `t1_artifact.json` with two fields: `artifact_id` set to the literal string `A.SOURCE` and a dummy `payload`.
- Use `pathlib` for cross‑platform path handling.
- Wrap file I/O in a `try/except` block and raise a `RuntimeError` on failure to make errors explicit.

### Template
```python
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
```

### Validation
```bash
# Run the producer
python t1_producer.py
# Verify the artifact exists and contains the expected ID
type artifacts\t1_artifact.json
# (On Unix you could use `cat` instead of `type`)
```

---

## Step 2: t2_consumer.py

### Why
T2 must consume the exact artifact ID produced by T1. This step validates the dependency and writes a marker file to prove successful consumption before the final report is generated.

### Design
- Load `artifacts/t1_artifact.json`.
- Verify that the `artifact_id` field equals the literal string `A.SOURCE`.
- If the ID does not match, raise a `ValueError` with a clear message.
- On success, write a simple marker file `artifacts/t2_success.txt`.
- All I/O errors are caught and re‑raised as `RuntimeError` for clarity.

### Template
```python
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
```

### Validation
```bash
# Run the consumer (after T1 has run)
python t2_consumer.py
# Verify the success marker exists
type artifacts\t2_success.txt
```

---

## Step 3: generate_report.py

### Why
The final deliverable `dependency_report.md` must be created **after** T2 has successfully consumed the artifact. This step reads the original artifact to embed the required word `A.SOURCE` in the report, satisfying the done criteria.

### Design
- Load the same JSON artifact (`artifacts/t1_artifact.json`).
- Extract the `artifact_id` value.
- Write a Markdown file `dependency_report.md` that includes the ID in bold text.
- Use explicit error handling for missing files or malformed JSON.

### Template
```python
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
```

### Validation
```bash
# Run the report generator (after T2 has run)
python generate_report.py
# Verify the report contains the required word
findstr "A.SOURCE" dependency_report.md
# (On Unix you could use `grep -q "A.SOURCE" dependency_report.md`)
```

---

*All three scripts are intentionally minimal, dependency‑free, and include comprehensive docstrings and error handling. Executing them in order (`t1_producer.py` → `t2_consumer.py` → `generate_report.py`) will produce `dependency_report.md` that satisfies the goal contract's done criteria.*
