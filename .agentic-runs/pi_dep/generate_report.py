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
