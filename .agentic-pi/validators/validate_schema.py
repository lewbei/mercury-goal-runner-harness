import json
import sys
from pathlib import Path

TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "boolean": bool
}

def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)

def validate(instance, schema, loc="$"):
    errors = []

    expected_type = schema.get("type")
    if expected_type:
        py_type = TYPE_MAP.get(expected_type)
        if py_type and not isinstance(instance, py_type):
            errors.append(f"{loc}: expected {expected_type}, got {type(instance).__name__}")
            return errors

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{loc}: value {instance!r} not in enum {schema['enum']}")

    if expected_type == "object":
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{loc}: missing required field {key}")

        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance.keys():
                if key not in props:
                    errors.append(f"{loc}: unexpected field {key}")

        for key, subschema in props.items():
            if key in instance:
                errors.extend(validate(instance[key], subschema, f"{loc}.{key}"))

    if expected_type == "array":
        item_schema = schema.get("items", {})
        for i, item in enumerate(instance):
            errors.extend(validate(item, item_schema, f"{loc}[{i}]"))

    return errors

def main():
    if len(sys.argv) != 3:
        print("Usage: python validate_schema.py <schema.json> <instance.json>")
        sys.exit(2)

    schema_path = Path(sys.argv[1])
    instance_path = Path(sys.argv[2])

    schema = load_json(schema_path)
    instance = load_json(instance_path)

    errors = validate(instance, schema)

    if errors:
        print("SCHEMA_INVALID")
        for e in errors:
            print(f"- {e}")
        sys.exit(1)

    print("SCHEMA_VALID")

if __name__ == "__main__":
    main()


