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
