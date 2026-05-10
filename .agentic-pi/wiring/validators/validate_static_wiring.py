"""validate_static_wiring.py

Validates that the static wiring between modules is complete.

Checks performed:
- Every declared input has at least one producer (some module lists it as output).
- Every declared output has at least one consumer (some module lists it as input).
- Modules with unresolved inputs or outputs are marked ``DECLARED_ONLY``.
- Fully resolved modules are marked ``STATIC_WIRED``.

Returns a dict mapping module name → status string.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Set


def validate_static_wiring(registry_path: Path) -> Dict[str, str]:
    """Perform the static wiring check and return per-module status.

    Args:
        registry_path: Path to ``module_registry.json``.

    Returns:
        A dict ``{module_name: "STATIC_WIRED" | "DECLARED_ONLY"}``.
    """
    with registry_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    # Build reverse lookups
    output_to_producer: Dict[str, str] = {}
    input_to_consumers: Dict[str, Set[str]] = {}

    for name, data in raw.items():
        outputs = data.get("outputs", [])
        for out in outputs:
            output_to_producer[out] = name
        inputs = data.get("inputs", [])
        for inp in inputs:
            input_to_consumers.setdefault(inp, set()).add(name)

    status: Dict[str, str] = {}
    for name, data in raw.items():
        inputs = data.get("inputs", [])
        outputs = data.get("outputs", [])
        missing_inputs = [i for i in inputs if i not in output_to_producer]
        missing_outputs = [o for o in outputs if o not in input_to_consumers]
        if missing_inputs or missing_outputs:
            status[name] = "DECLARED_ONLY"
        else:
            status[name] = "STATIC_WIRED"

    return status


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate static wiring")
    parser.add_argument("path", type=Path, help="Path to module_registry.json")
    args = parser.parse_args()

    result = validate_static_wiring(args.path)
    for mod, stat in sorted(result.items()):
        print(f"  {mod}: {stat}")


if __name__ == "__main__":
    main()
