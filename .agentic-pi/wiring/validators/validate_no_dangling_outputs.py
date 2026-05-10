"""validate_no_dangling_outputs.py

Validates that every declared output in the module registry has at least one
consumer (i.e., another module lists it as an input).

Outputs that no module consumes are "dangling" and indicate a wiring gap.

Returns a list of (module_name, output_name) tuples for dangling outputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Set, Tuple


def find_dangling_outputs(registry_path: Path) -> List[Tuple[str, str]]:
    """Return a list of (module_name, output_name) for every dangling output.

    A dangling output is one that is declared by a module but not listed as
    an input of any other module.
    """
    with registry_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    # Collect all declared inputs across all modules
    all_inputs: Set[str] = set()
    for data in raw.values():
        all_inputs.update(data.get("inputs", []))

    dangling: List[Tuple[str, str]] = []
    for name, data in raw.items():
        for out in data.get("outputs", []):
            if out not in all_inputs:
                dangling.append((name, out))

    return dangling


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Find dangling outputs")
    parser.add_argument("path", type=Path, help="Path to module_registry.json")
    args = parser.parse_args()

    dangling = find_dangling_outputs(args.path)
    if dangling:
        print(f"Found {len(dangling)} dangling output(s):")
        for mod, out in dangling:
            print(f"  {mod} -> {out}")
        exit(1)
    else:
        print("No dangling outputs found.")
        exit(0)


if __name__ == "__main__":
    main()
