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
