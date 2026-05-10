# Thinking Plan: Two-step artifact dependency proof

## Architecture
We implement the goal using two independent Python scripts that run sequentially.
- **create_source.py** (T1) creates the source artifact `source.txt`. This file represents artifact ID `A.SOURCE`.
- **generate_report.py** (T2) reads `source.txt` and generates `dependency_report.md` containing the literal word `A.SOURCE`.

Both scripts are tiny, have no external dependencies beyond the Python standard library, and use `pathlib` for OS‑agnostic file handling. The scripts live in the same directory as the plan, making the data flow explicit and easy to validate.

## Design decisions
- **Separate scripts per task** – isolates responsibilities, mirrors the two‑step artifact dependency model, and simplifies validation.
- **Plain‑text artifact (`source.txt`)** – easiest to create/read on any platform; no binary handling needed.
- **Explicit error handling** – each script checks for I/O errors and exits with a non‑zero status, ensuring failure is detectable.
- **Embedding the identifier** – `generate_report.py` writes the exact string `A.SOURCE` into the markdown report, satisfying the `done_criteria`.
- **Standard library only** – avoids extra package installation, keeping the harness lightweight.

---

## Step 1: create_source.py

### Why
T1 must produce the source artifact `source.txt` (artifact ID `A.SOURCE`). This step establishes the required input for T2.

### Design
The script writes a placeholder text to `source.txt`. It uses `pathlib.Path` to locate the file relative to the script location, writes UTF‑8 encoded text, and prints a success message. Errors during file creation are caught and reported, causing the script to exit with status 1.

### Template
```python
# create_source.py
"""Creates the source artifact A.SOURCE as source.txt.

The file contains a placeholder text. This script is the first task (T1) in the
artifact dependency proof.
"""

import pathlib
import sys

def main() -> None:
    """Write source.txt with placeholder content."""
    # Resolve the target path relative to this script
    target_path = pathlib.Path(__file__).with_name("source.txt")
    try:
        target_path.write_text("Placeholder content for A.SOURCE.\n", encoding="utf-8")
        print(f"Created artifact at {target_path}")
    except OSError as e:
        print(f"Failed to write source.txt: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Validation
```bash
python create_source.py && type source.txt
```
The command should create `source.txt` and display its contents.

---

## Step 2: generate_report.py

### Why
T2 depends on the artifact produced by T1. It must read `source.txt` and create `dependency_report.md` containing the word `A.SOURCE`.

### Design
The script verifies that `source.txt` exists, reads it (ensuring it is readable), then writes a markdown report that includes the literal identifier `A.SOURCE`. Errors are handled explicitly, with clear messages and non‑zero exit codes.

### Template
```python
# generate_report.py
"""Reads the source artifact A.SOURCE (source.txt) and creates a dependency
report containing the identifier 'A.SOURCE'.

This script is the second task (T2) and demonstrates the artifact dependency.
"""

import pathlib
import sys

def main() -> None:
    """Read source.txt and write dependency_report.md."""
    source_path = pathlib.Path(__file__).with_name("source.txt")
    report_path = pathlib.Path(__file__).with_name("dependency_report.md")
    # Verify source exists
    if not source_path.is_file():
        print(f"Source artifact not found at {source_path}", file=sys.stderr)
        sys.exit(1)
    # Read source content (ensures readability)
    try:
        _ = source_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"Failed to read source.txt: {e}", file=sys.stderr)
        sys.exit(1)
    # Write report containing the word A.SOURCE
    report_content = "# Dependency Report\n\nThe artifact ID required is **A.SOURCE**.\n"
    try:
        report_path.write_text(report_content, encoding="utf-8")
        print(f"Created report at {report_path}")
    except OSError as e:
        print(f"Failed to write dependency_report.md: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Validation
```bash
python generate_report.py && type dependency_report.md
```
The command should create `dependency_report.md` and display its contents, which must include the word `A.SOURCE`.

---
