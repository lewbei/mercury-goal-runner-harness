# Thinking Plan: Two-step artifact dependency

## Architecture
We use a minimal two‑script architecture that mirrors the two‑step artifact workflow described in the goal contract.

- **t1_create_source.py** – Generates the source artifact `artifacts/source.txt` containing the identifier `A.SOURCE`.
- **t2_create_report.py** – Consumes `artifacts/source.txt` and produces `artifacts/dependency_report.md` which must contain the word `A.SOURCE`.

All artifacts live under a dedicated `artifacts/` directory to keep the repository root clean (satisfying the explicit constraint "Do not write benchmark outputs to the repo root").  The scripts are pure Python 3 code using only the standard library (`pathlib`, `sys`).  This makes the solution portable across the Windows execution environment used by the harness.

## Design decisions
| Decision | Alternatives considered | Chosen option | Rationale |
|----------|--------------------------|---------------|-----------|
| **Single script vs two scripts** | One script could both write the source and the report. | Two separate scripts. | The goal explicitly describes a two‑step dependency (T1 → T2).  Keeping them separate enforces the artifact hand‑off and mirrors real‑world pipelines. |
| **Artifact format** | JSON, binary, or plain text. | Plain text for `source.txt`; Markdown for `dependency_report.md`. | Simpler I/O, no parsing overhead, and the required word `A.SOURCE` can be verified with a simple string search. |
| **Path handling** | Hard‑coded strings, relative paths, or `pathlib.Path`. | `pathlib.Path` with `Path(__file__).parent / "artifacts"`. | `pathlib` provides OS‑independent path manipulation and automatic directory creation, reducing bugs on Windows. |
| **Error handling** | Silent failures, exit codes, or explicit exceptions. | Explicit `raise` with clear messages and exit status `1`. | Makes debugging straightforward and ensures the harness can detect failure via non‑zero exit codes. |
| **CLI interface** | No CLI, `argparse`, or environment variables. | Minimal CLI using `sys.argv` for optional custom paths. | Keeps the scripts simple while still allowing flexibility for future testing. |

---

## Step 1: t1_create_source.py

### Why
This step establishes the primary artifact `A.SOURCE`.  It must run before any downstream task can read the source file, so it is the logical first step.

### Design
- Provide a `create_source(output_path: Path, content: str = "A.SOURCE") -> None` function.
- Ensure the parent directory exists (`output_path.parent.mkdir(parents=True, exist_ok=True)`).
- Write `content` to `output_path` using UTF‑8 encoding.
- Raise `OSError` if the write fails.
- Include a `main()` guard that parses optional command‑line arguments for custom output location.
- Use `sys.exit(0)` on success and `sys.exit(1)` on any uncaught exception.

### Template
```python
# t1_create_source.py
"""Generate the source artifact `source.txt` containing the identifier `A.SOURCE`.

The script is deliberately simple: it writes a single line of text to the
`artifacts/` directory.  The function can be imported and reused, but the script
can also be executed directly.
"""

from __future__ import annotations

import sys
from pathlib import Path


def create_source(output_path: Path, content: str = "A.SOURCE") -> None:
    """Create the source file.

    Parameters
    ----------
    output_path: Path
        Full path to the file that will be created.
    content: str, optional
        Text to write.  Defaults to the required identifier ``"A.SOURCE"``.

    Raises
    ------
    OSError
        If the file cannot be written for any reason.
    """
    # Ensure the directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        output_path.write_text(content, encoding="utf-8")
    except Exception as exc:
        raise OSError(f"Failed to write source file at {output_path}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    """Entry point for the script.

    Optional command‑line argument ``<output_path>`` can override the default
    location ``artifacts/source.txt``.
    """
    if argv is None:
        argv = sys.argv[1:]
    # Default location relative to this script
    default_path = Path(__file__).parent / "artifacts" / "source.txt"
    output_path = Path(argv[0]) if argv else default_path
    try:
        create_source(output_path)
    except OSError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### Validation
Run the script and verify the artifact:
```bash
python t1_create_source.py
# Verify existence and content
if not " "artifacts/source.txt"; then echo "Missing source.txt"; exit 1; fi
if not find "artifacts/source.txt" -type f -exec grep -q "A.SOURCE" {} +; then echo "Incorrect content"; exit 1; fi
```

---

## Step 2: t2_create_report.py

### Why
This step depends on the artifact produced by Step 1.  It reads ``artifacts/source.txt`` and
creates ``artifacts/dependency_report.md`` which must contain the word ``A.SOURCE``.

### Design
- Provide a `create_report(source_path: Path, report_path: Path) -> None` function.
- Read the source file; raise `FileNotFoundError` if missing.
- Verify the source content contains the exact token ``A.SOURCE``; raise `ValueError` otherwise.
- Write a markdown report that includes the required word.  The report can be a simple
  single‑paragraph document.
- Ensure the report directory exists.
- Include a CLI entry point similar to Step 1, allowing optional custom paths.
- Exit with status `0` on success, `1` on any error.

### Template
```python
# t2_create_report.py
"""Consume the source artifact and produce a markdown report.

The report must contain the identifier ``A.SOURCE`` verbatim.  This script
verifies the source file before generating the report, guaranteeing the
``done_criteria`` of the goal contract.
"""

from __future__ import annotations

import sys
from pathlib import Path


def create_report(source_path: Path, report_path: Path) -> None:
    """Read ``source_path`` and write a markdown report to ``report_path``.

    Parameters
    ----------
    source_path: Path
        Path to the source artifact generated by Step 1.
    report_path: Path
        Destination for the markdown report.

    Raises
    ------
    FileNotFoundError
        If ``source_path`` does not exist.
    ValueError
        If the source content does not contain the required token ``A.SOURCE``.
    OSError
        If the report cannot be written.
    """
    if not source_path.is_file():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    content = source_path.read_text(encoding="utf-8")
    if "A.SOURCE" not in content:
        raise ValueError("Source file does not contain the required token 'A.SOURCE'.")
    # Ensure the report directory exists
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_md = f"# Dependency Report\n\nThe source artifact contains the identifier **A.SOURCE**.\n"
    try:
        report_path.write_text(report_md, encoding="utf-8")
    except Exception as exc:
        raise OSError(f"Failed to write report at {report_path}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    """Entry point for the script.

    Optional arguments: ``<source_path>`` ``<report_path>``.
    """
    if argv is None:
        argv = sys.argv[1:]
    default_source = Path(__file__).parent / "artifacts" / "source.txt"
    default_report = Path(__file__).parent / "artifacts" / "dependency_report.md"
    source_path = Path(argv[0]) if len(argv) >= 1 else default_source
    report_path = Path(argv[1]) if len(argv) >= 2 else default_report
    try:
        create_report(source_path, report_path)
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### Validation
Run the second script after Step 1 and verify the report:
```bash
python t2_create_report.py
# Verify existence
if not test -f "artifacts/dependency_report.md"; then echo "Missing report"; exit 1; fi
# Verify content contains the required word
if not grep -q "A.SOURCE" "artifacts/dependency_report.md"; then echo "Report missing token"; exit 1; fi
```

---

## Summary
The two‑step plan satisfies the goal contract:
1. `t1_create_source.py` creates the artifact `A.SOURCE` (`source.txt`).
2. `t2_create_report.py` reads that artifact and produces `dependency_report.md` containing the word `A.SOURCE`.
Both scripts are self‑contained, use only the Python standard library, and place all generated files under the `artifacts/` folder, respecting the repository constraints.
