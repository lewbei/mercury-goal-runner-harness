# Thinking Plan: CLI CSV Summary Tool

## Architecture
We will implement the entire functionality in a single Python script `cli_tool.py`. The script will use only the Python standard library (`argparse`, `csv`, `os`, `sys`). It will provide a command‑line interface, read the CSV file, count rows and columns, and print a concise summary. No additional modules or configuration files are required, which keeps the project minimal and satisfies the goal's constraints.

## Design decisions
- **CLI parsing**: Use `argparse` instead of manual `sys.argv` parsing because it automatically generates help text, validates arguments, and is part of the stdlib.
- **CSV handling**: Use the `csv` module rather than manual string splitting to correctly handle quoting, delimiters, and line endings.
- **Row/column counting**: Iterate over the CSV rows, increment a row counter, and track the maximum number of columns observed (handles irregular rows). This approach works for any CSV shape and avoids loading the whole file into memory.
- **Error handling**: Explicitly catch `FileNotFoundError`, `PermissionError`, and `csv.Error` to provide user‑friendly messages and exit with a non‑zero status. A generic `Exception` fallback ensures unexpected errors are also reported.
- **Output format**: Print two lines – `Rows: <count>` and `Columns: <count>` – satisfying the test requirement that at least two lines containing the words "Rows" and "Columns" are produced.
- **Alternatives considered**:
  - *Option A*: Use third‑party `pandas` for CSV handling – rejected because external dependencies are forbidden.
  - *Option B*: Manual parsing with `str.split` – rejected due to edge‑case handling (quoted commas, newlines).
  - *Option C*: Use the stdlib `csv` module – chosen for correctness and compliance.

---

## Step 1: cli_tool.py

### Why
The CLI script is the sole artifact required by the goal contract. Creating it first establishes the entry point, argument handling, and core logic needed for the summary. All subsequent testing and validation depend on this file existing and functioning.

### Design
- **Entry point**: `if __name__ == "__main__": main()`
- **Argument parsing**: `argparse.ArgumentParser` with a single positional argument for the CSV path.
- **File validation**: Verify the path exists and is a regular file before attempting to open.
- **CSV reading**: Open the file with `newline=""` and `encoding="utf-8"`, use `csv.reader` to iterate rows.
- **Counting logic**: Increment `row_count` per iteration; update `max_columns` with `max(max_columns, len(row))`.
- **Edge cases**:
  - Empty file → both counts remain `0`.
  - Inconsistent row lengths → column count reflects the widest row (most informative).
  - Non‑existent or unreadable file → clear error message and exit code `1`.
- **Output**: Print two lines: `Rows: <row_count>` and `Columns: <max_columns>`.
- **Error handling**: Catch and report `FileNotFoundError`, `PermissionError`, `csv.Error`, and any other unexpected exception, exiting with code `1`.

### Template
```python
# cli_tool.py
"""
CLI tool to read a CSV file and print a summary of row and column counts.

Usage:
    python cli_tool.py <csv_file>

The script prints:
    Rows: <num_rows>
    Columns: <num_columns>
"""

import argparse
import csv
import sys
import os


def parse_arguments() -> argparse.Namespace:
    """Parse command‑line arguments."""
    parser = argparse.ArgumentParser(
        description="Read a CSV file and print row and column counts."
    )
    parser.add_argument(
        "csv_path",
        metavar="CSV_FILE",
        help="Path to the CSV file to process."
    )
    return parser.parse_args()


def count_rows_and_columns(csv_path: str) -> tuple[int, int]:
    """Count rows and columns in the CSV file.

    Parameters
    ----------
    csv_path : str
        Path to the CSV file.

    Returns
    -------
    tuple[int, int]
        (row_count, column_count)

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    PermissionError
        If the file cannot be opened due to permission issues.
    csv.Error
        If the file is not a valid CSV.
    """
    row_count = 0
    max_columns = 0

    with open(csv_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            row_count += 1
            max_columns = max(max_columns, len(row))

    return row_count, max_columns


def main() -> None:
    """Entry point for the CLI tool."""
    args = parse_arguments()
    csv_path = args.csv_path

    # Validate that the path exists and is a file
    if not os.path.isfile(csv_path):
        print(f"Error: '{csv_path}' does not exist or is not a file.", file=sys.stderr)
        sys.exit(1)

    try:
        rows, cols = count_rows_and_columns(csv_path)
    except FileNotFoundError:
        print(f"Error: File '{csv_path}' not found.", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: Permission denied when accessing '{csv_path}'.", file=sys.stderr)
        sys.exit(1)
    except csv.Error as e:
        print(f"Error: Failed to parse CSV file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Catch‑all for unexpected errors
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

    # Print summary – at least two lines as required by the test
    print(f"Rows: {rows}")
    print(f"Columns: {cols}")

if __name__ == "__main__":
    main()
```

### Validation
To verify the step works, run the following commands in a terminal inside the project directory:

```bash
# 1. Create a sample CSV file
printf "a,b,c\n1,2,3\n4,5,6\n" > data.csv

# 2. Execute the CLI tool
python cli_tool.py data.csv

# Expected output (order of lines may vary but both must appear):
# Rows: 3
# Columns: 3

# 3. Check exit code (should be 0)
echo $?
```
The script should exit with code `0` and the stdout should contain the words `Rows` and `Columns` on separate lines, satisfying the `CLI_SUMMARY_TEST` defined in the goal contract.
