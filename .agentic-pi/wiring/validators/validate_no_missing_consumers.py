"""validate_no_missing_consumers.py

Validates that every declared input in the module registry has at least one
producer (i.e., some module lists it as an output).

Inputs that no module produces are "missing" and indicate a wiring gap.

Returns a list of (module_name, input_name) tuples for missing consumers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Set, Tuple


def find_missing_consumers(registry_path: Path) -> List[Tuple[str, str]]:
    """Return a list of (module_name, input_name) for every missing consumer.

    A missing consumer is an input that is declared by a module but not
    produced as an output by any other module.
    """
    with registry_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    # Collect all declared outputs across all modules
    all_outputs: Set[str] = set()
    for data in raw.values():
        all_outputs.update(data.get("outputs", []))

    missing: List[Tuple[str, str]] = []
    for name, data in raw.items():
        for inp in data.get("inputs", []):
            if inp not in all_outputs:
                missing.append((name, inp))

    return missing


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Find missing consumers")
    parser.add_argument("path", type=Path, help="Path to module_registry.json")
    args = parser.parse_args()

    missing = find_missing_consumers(args.path)
    if missing:
        print(f"Found {len(missing)} missing consumer(s):")
        for mod, inp in missing:
            print(f"  {mod} needs input {inp!r} which has no producer")
        exit(1)
    else:
        print("No missing consumers found.")
        exit(0)


if __name__ == "__main__":
    main()
