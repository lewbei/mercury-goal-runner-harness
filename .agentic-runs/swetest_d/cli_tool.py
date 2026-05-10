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
