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
