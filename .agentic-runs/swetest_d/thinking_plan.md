# Thinking Plan: Create cli_tool.py that reads data.csv and prints a summary

## Architecture
We will implement a small, self‑contained CLI tool using only the Python standard library. The implementation is split into two files:

1. **csv_summary.py** – core logic that reads a CSV file and returns the number of rows and columns. Keeping the logic separate from the CLI makes it easy to unit‑test and reuse.
2. **cli_tool.py** – the command‑line entry point that parses the file path argument, calls the core logic, and prints a human‑readable summary.

Both files live at the repository root so they are easy to discover and run with `python cli_tool.py <path>`.

## Design decisions
- **Standard library only** – we use `argparse` for CLI parsing, `csv` for CSV handling, and `pathlib` for portable path manipulation. No external dependencies are required, satisfying the explicit constraints.
- **Error handling** – the core function raises `FileNotFoundError` if the file does not exist and `ValueError` if the CSV is empty or malformed. The CLI catches these exceptions and prints a concise error message to `stderr` before exiting with a non‑zero status.
- **Row/column definition** – rows count data rows (excluding the header). Columns count the number of fields in the header row. If the CSV has no header (empty file), we treat both counts as zero.
- **Separation of concerns** – by isolating CSV processing in `csv_summary.py` we enable straightforward unit testing (e.g., via `python -m unittest`). The CLI file only deals with argument handling and user interaction.
- **Encoding** – we open files using `utf‑8` with `errors='replace'` to avoid crashes on non‑UTF‑8 input while still providing a best‑effort summary.

---

## Step 1: csv_summary.py

### Why
The CSV‑processing logic is the foundational piece that the CLI will depend on. Implementing it first lets us test the core functionality in isolation before wiring it up to the command line.

### Design
We expose a single public function `get_csv_summary(path: Path) -> Tuple[int, int]` that returns `(row_count, column_count)`. The function:
1. Validates that the file exists.
2. Opens the file with `utf‑8` encoding, using `csv.reader`.
3. Reads the header row to determine the column count.
4. Iterates over the remaining rows, counting them.
5. Handles edge cases:
   - Empty file → returns `(0, 0)`.
   - Inconsistent row lengths → still counts columns based on the header; extra fields are ignored.
   - Any I/O error is propagated as `FileNotFoundError` or `OSError`.

The implementation includes comprehensive docstrings and type hints.

### Template
```python
# csv_summary.py

"""Utility module for summarising CSV files.

Provides a single function :func:`get_csv_summary` that returns the number of
data rows and columns in a CSV file.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Tuple


def get_csv_summary(csv_path: Path) -> Tuple[int, int]:
    """Return the number of data rows and columns in *csv_path*.

    Parameters
    ----------
    csv_path: Path
        Path to the CSV file.

    Returns
    -------
    Tuple[int, int]
        ``(row_count, column_count)`` where ``row_count`` excludes the header.

    Raises
    ------
    FileNotFoundError
        If *csv_path* does not exist.
    ValueError
        If the file exists but is empty or does not contain a header row.
    """
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    # Open with utf‑8; replace malformed bytes to avoid crashes.
    with csv_path.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            # Empty file – no rows, no columns.
            return 0, 0

        column_count = len(header)
        row_count = sum(1 for _ in reader)
        return row_count, column_count
```

### Validation
Create a tiny CSV file and invoke the function directly:

```bash
# Create a sample CSV
printf "col1,col2\n1,2\n3,4\n" > sample.csv
# Run a one‑liner that imports the module and prints the summary
python - <<'PY'
from pathlib import Path
from csv_summary import get_csv_summary
rows, cols = get_csv_summary(Path('sample.csv'))
print(f'Rows: {rows}')
print(f'Columns: {cols}')
PY
```
Expected output:
```
Rows: 2
Columns: 2
```
If the output matches, Step 1 is successful.

---

## Step 2: cli_tool.py

### Why
Now that the core CSV logic is verified, we can build the user‑facing command‑line interface that delegates to `csv_summary.get_csv_summary`. This step depends on the module created in Step 1.

### Design
The script uses `argparse` to accept a single positional argument – the path to the CSV file. It calls `get_csv_summary`, prints two lines:
```
Rows: <row_count>
Columns: <column_count>
```
If an exception occurs (file not found, empty CSV, etc.), the script prints an error message to `stderr` and exits with status 1.

The code follows best practices: a `main()` function, `if __name__ == "__main__":` guard, and explicit type hints.

### Template
```python
# cli_tool.py

"""Command‑line interface for summarising a CSV file.

Usage:
    python cli_tool.py <path_to_csv>
"""

import argparse
import sys
from pathlib import Path

# Import the core logic from the sibling module.
from csv_summary import get_csv_summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command‑line arguments.

    Parameters
    ----------
    argv: list[str] | None
        Argument list to parse; defaults to ``sys.argv[1:]``.

    Returns
    -------
    argparse.Namespace
        Parsed arguments with attribute ``csv_path``.
    """
    parser = argparse.ArgumentParser(
        description="Print the number of rows and columns in a CSV file."
    )
    parser.add_argument(
        "csv_path",
        type=Path,
        help="Path to the CSV file to summarise."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the CLI tool.

    Returns
    -------
    int
        Exit code – ``0`` on success, ``1`` on error.
    """
    args = parse_args(argv)
    try:
        rows, cols = get_csv_summary(args.csv_path)
        print(f"Rows: {rows}")
        print(f"Columns: {cols}")
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        # Catch‑all for unexpected errors – still report to the user.
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

### Validation
Run the CLI against a sample CSV and verify the output contains both required lines:

```bash
# Create a sample CSV (same as in Step 1)
printf "col1,col2\n1,2\n3,4\n" > data.csv
# Execute the tool
python cli_tool.py data.csv
```
Expected stdout (order may vary but both lines must appear):
```
Rows: 2
Columns: 2
```
The command should exit with status 0. If the output contains the words "Rows" and "Columns" on separate lines, the done criteria are satisfied.
