#!/usr/bin/env python3
"""Mini JSON Schema validator for deterministic harness artifacts.

Supports: type, enum, const, required, properties, additionalProperties,
minLength, minItems, pattern, minimum, maximum, oneOf, anyOf, $ref/$defs.

This is intentionally a single-file validator with no external dependencies
so that schema-valid checks work in any Python 3.9+ environment without
installing jsonschema.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

TYPE_MAP: dict[str, type] = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _check_type(instance: Any, expected: str) -> bool:
    py_type = TYPE_MAP.get(expected)
    if py_type is None:
        return True  # unknown type, skip
    if isinstance(py_type, tuple):
        return isinstance(instance, py_type)
    return isinstance(instance, py_type)


# ── format validators ─────────────────────────────────────────────────────────

_FORMAT_VALIDATORS: dict[str, re.Pattern] = {
    "date-time": re.compile(
        r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
    ),
    "date": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "time": re.compile(r"^\d{2}:\d{2}:\d{2}"),
    "uri": re.compile(r"^https?://"),
    "email": re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    "ipv4": re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"),
    "uuid": re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE,
    ),
}


# ── core validator ────────────────────────────────────────────────────────────


def validate(
    instance: Any,
    schema: dict,
    loc: str = "$",
    *,
    root_schema: dict | None = None,
) -> list[str]:
    """Validate an instance against a JSON Schema subset.

    Args:
        instance: The value to validate.
        schema: JSON Schema dict (must have been loaded from a file).
        loc: JSON path for error messages (e.g. "$.foo[0].bar").
        root_schema: The top-level schema document (for $ref resolution).
            If omitted, schema is used as the root.

    Returns:
        List of error strings (empty = valid).
    """
    if root_schema is None:
        root_schema = schema

    errors: list[str] = []

    # ── $ref ──────────────────────────────────────────────────────────────
    if "$ref" in schema:
        ref = schema["$ref"]
        resolved = _resolve_ref(ref, root_schema, loc)
        if isinstance(resolved, str):
            errors.append(resolved)
            return errors
        # resolved is a dict — validate against it
        return validate(instance, resolved, loc, root_schema=root_schema)

    # ── const ─────────────────────────────────────────────────────────────
    if "const" in schema:
        if instance != schema["const"]:
            errors.append(
                f"{loc}: value {instance!r} does not match const {schema['const']!r}"
            )
        return errors

    # ── enum ──────────────────────────────────────────────────────────────
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(
            f"{loc}: value {instance!r} not in enum {schema['enum']}"
        )

    # ── type ──────────────────────────────────────────────────────────────
    expected_type = schema.get("type")
    if expected_type:
        # Allow "type" to be a list (e.g. ["string", "null"])
        if isinstance(expected_type, list):
            if not any(_check_type(instance, t) for t in expected_type):
                errors.append(
                    f"{loc}: expected one of {expected_type}, got {type(instance).__name__}"
                )
                return errors
        elif not _check_type(instance, expected_type):
            errors.append(
                f"{loc}: expected {expected_type}, got {type(instance).__name__}"
            )
            return errors

    # ── oneOf / anyOf ─────────────────────────────────────────────────────
    if "oneOf" in schema:
        sub_results = [
            validate(instance, sub, f"{loc}[oneOf/{i}]", root_schema=root_schema)
            for i, sub in enumerate(schema["oneOf"])
        ]
        passing = [i for i, r in enumerate(sub_results) if not r]
        if len(passing) != 1:
            errors.append(
                f"{loc}: oneOf requires exactly 1 match, got {len(passing)} "
                f"(passing indices: {passing})"
            )

    if "anyOf" in schema:
        sub_results = [
            validate(instance, sub, f"{loc}[anyOf/{i}]", root_schema=root_schema)
            for i, sub in enumerate(schema["anyOf"])
        ]
        passing = [i for i, r in enumerate(sub_results) if not r]
        if not passing:
            errors.append(
                f"{loc}: anyOf requires at least 1 match, got 0"
            )

    # ── string constraints ────────────────────────────────────────────────
    if expected_type == "string" and isinstance(instance, str):
        min_length = schema.get("minLength")
        if min_length is not None and len(instance) < min_length:
            errors.append(
                f"{loc}: string length {len(instance)} < minLength {min_length}"
            )

        max_length = schema.get("maxLength")
        if max_length is not None and len(instance) > max_length:
            errors.append(
                f"{loc}: string length {len(instance)} > maxLength {max_length}"
            )

        pattern = schema.get("pattern")
        if pattern is not None:
            try:
                if not re.search(pattern, instance):
                    errors.append(
                        f"{loc}: string {instance!r} does not match pattern {pattern!r}"
                    )
            except re.error as e:
                errors.append(
                    f"{loc}: invalid pattern {pattern!r}: {e}"
                )

        fmt = schema.get("format")
        if fmt is not None:
            fmt_re = _FORMAT_VALIDATORS.get(fmt)
            if fmt_re and not fmt_re.search(instance):
                errors.append(
                    f"{loc}: string {instance!r} does not match format {fmt!r}"
                )

    # ── numeric constraints ───────────────────────────────────────────────
    if expected_type in ("integer", "number") and isinstance(instance, (int, float)):
        minimum = schema.get("minimum")
        if minimum is not None and instance < minimum:
            errors.append(
                f"{loc}: value {instance} < minimum {minimum}"
            )

        maximum = schema.get("maximum")
        if maximum is not None and instance > maximum:
            errors.append(
                f"{loc}: value {instance} > maximum {maximum}"
            )

        exclusive_minimum = schema.get("exclusiveMinimum")
        if exclusive_minimum is not None and instance <= exclusive_minimum:
            errors.append(
                f"{loc}: value {instance} <= exclusiveMinimum {exclusive_minimum}"
            )

        exclusive_maximum = schema.get("exclusiveMaximum")
        if exclusive_maximum is not None and instance >= exclusive_maximum:
            errors.append(
                f"{loc}: value {instance} >= exclusiveMaximum {exclusive_maximum}"
            )

        multiple_of = schema.get("multipleOf")
        if multiple_of is not None and instance % multiple_of != 0:
            errors.append(
                f"{loc}: value {instance} is not a multiple of {multiple_of}"
            )

    # ── array constraints ─────────────────────────────────────────────────
    if expected_type == "array" and isinstance(instance, list):
        min_items = schema.get("minItems")
        if min_items is not None and len(instance) < min_items:
            errors.append(
                f"{loc}: array length {len(instance)} < minItems {min_items}"
            )

        max_items = schema.get("maxItems")
        if max_items is not None and len(instance) > max_items:
            errors.append(
                f"{loc}: array length {len(instance)} > maxItems {max_items}"
            )

        unique_items = schema.get("uniqueItems")
        if unique_items and len(instance) != len(set(json.dumps(i, sort_keys=True) for i in instance)):
            errors.append(f"{loc}: array items are not unique")

        item_schema = schema.get("items", {})
        for i, item in enumerate(instance):
            errors.extend(
                validate(item, item_schema, f"{loc}[{i}]", root_schema=root_schema)
            )

    # ── object constraints ────────────────────────────────────────────────
    if expected_type == "object" and isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{loc}: missing required field {key!r}")

        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errors.append(f"{loc}: unexpected field {key!r}")

        min_properties = schema.get("minProperties")
        if min_properties is not None and len(instance) < min_properties:
            errors.append(
                f"{loc}: object has {len(instance)} properties, < minProperties {min_properties}"
            )

        max_properties = schema.get("maxProperties")
        if max_properties is not None and len(instance) > max_properties:
            errors.append(
                f"{loc}: object has {len(instance)} properties, > maxProperties {max_properties}"
            )

        for key, subschema in props.items():
            if key in instance:
                errors.extend(
                    validate(instance[key], subschema, f"{loc}.{key}", root_schema=root_schema)
                )

        # patternProperties (basic support)
        pattern_props = schema.get("patternProperties", {})
        if pattern_props:
            for key in instance:
                if key not in props:  # only check if not already in properties
                    for pat_str, pat_schema in pattern_props.items():
                        try:
                            if re.search(pat_str, key):
                                errors.extend(
                                    validate(
                                        instance[key],
                                        pat_schema,
                                        f"{loc}.{key}",
                                        root_schema=root_schema,
                                    )
                                )
                        except re.error:
                            pass

    return errors


# ── $ref resolution ───────────────────────────────────────────────────────────


def _resolve_ref(ref: str, root_schema: dict, loc: str) -> dict | str:
    """Resolve a $ref pointer within root_schema.

    Returns the resolved schema dict, or an error string.
    """
    if not ref.startswith("#/"):
        return f"{loc}: only local $ref (starting with #/) is supported, got {ref!r}"

    parts = ref[2:].split("/")
    current: Any = root_schema
    for part in parts:
        # Unescape ~0 -> ~, ~1 -> /
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return (
                f"{loc}: $ref {ref!r} not found: "
                f"missing key {part!r} at {type(current).__name__}"
            )

    if not isinstance(current, dict):
        return f"{loc}: $ref {ref!r} resolved to non-object {type(current).__name__}"

    return current


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python validate_schema.py <schema.json> <instance.json>")
        return 2

    schema_path = Path(sys.argv[1])
    instance_path = Path(sys.argv[2])

    schema = load_json(schema_path)
    instance = load_json(instance_path)

    errors = validate(instance, schema)

    if errors:
        print("SCHEMA_INVALID")
        for e in errors:
            print(f"- {e}")
        return 1

    print("SCHEMA_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
