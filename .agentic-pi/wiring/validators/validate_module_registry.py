"""validate_module_registry.py

Validates that a module_registry.json file conforms to the expected schema.

Checks performed:
- Top-level value must be a JSON object (dict).
- Each key must be a non-empty string (module name).
- Each module value must be a dict.
- Each module dict must have optional keys: ``inputs``, ``outputs``,
  ``downstream_consumers``, ``command``.
- ``inputs``, ``outputs``, ``downstream_consumers`` must be lists of strings.
- ``command`` must be a string.

Returns a list of validation error messages (empty if valid).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any


def validate_registry(registry_path: Path) -> List[str]:
    """Load and validate ``module_registry.json``.

    Args:
        registry_path: Path to the JSON file.

    Returns:
        A list of error messages.  An empty list means the file is valid.
    """
    errors: List[str] = []

    if not registry_path.is_file():
        errors.append(f"File not found: {registry_path}")
        return errors

    try:
        with registry_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {registry_path}: {exc}")
        return errors

    if not isinstance(raw, dict):
        errors.append(f"Top-level value must be a JSON object, got {type(raw).__name__}")
        return errors

    for module_name, module_data in raw.items():
        if not isinstance(module_name, str) or not module_name.strip():
            errors.append(f"Module key must be a non-empty string, got {module_name!r}")
            continue

        if not isinstance(module_data, dict):
            errors.append(f"Module {module_name!r} value must be a dict, got {type(module_data).__name__}")
            continue

        # Validate optional fields
        for field_name in ("inputs", "outputs", "downstream_consumers"):
            value = module_data.get(field_name)
            if value is not None:
                if not isinstance(value, list):
                    errors.append(
                        f"Module {module_name!r}.{field_name} must be a list, "
                        f"got {type(value).__name__}"
                    )
                else:
                    for i, item in enumerate(value):
                        if not isinstance(item, str):
                            errors.append(
                                f"Module {module_name!r}.{field_name}[{i}] must be a string, "
                                f"got {type(item).__name__}"
                            )

        command = module_data.get("command")
        if command is not None and not isinstance(command, str):
            errors.append(
                f"Module {module_name!r}.command must be a string, "
                f"got {type(command).__name__}"
            )

    return errors


def main() -> None:
    """CLI entry point for standalone validation."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate module_registry.json")
    parser.add_argument("path", type=Path, help="Path to module_registry.json")
    args = parser.parse_args()

    errors = validate_registry(args.path)
    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        exit(1)
    else:
        print(f"{args.path} is valid.")
        exit(0)


if __name__ == "__main__":
    main()
