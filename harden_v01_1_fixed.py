from pathlib import Path
import json

# 1. Harden step_result schema
schema_path = Path(".agentic-pi/schemas/step_result.schema.json")
schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))

schema["properties"]["action_taken"]["minLength"] = 1
schema["properties"]["files_touched"]["minItems"] = 1
schema["properties"]["files_touched"]["items"]["minLength"] = 1
schema["properties"]["evidence"]["minItems"] = 1
schema["properties"]["evidence"]["items"]["minLength"] = 1

schema_path.write_text(
    json.dumps(schema, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

# 2. Rewrite validator with minLength/minItems support
validator_path = Path(".agentic-pi/validators/validate_schema.py")
validator_code = r'''import json
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

    if expected_type == "string":
        min_length = schema.get("minLength")
        if min_length is not None and len(instance) < min_length:
            errors.append(f"{loc}: string length {len(instance)} < minLength {min_length}")

    if expected_type == "array":
        min_items = schema.get("minItems")
        if min_items is not None and len(instance) < min_items:
            errors.append(f"{loc}: array length {len(instance)} < minItems {min_items}")

        item_schema = schema.get("items", {})
        for i, item in enumerate(instance):
            errors.extend(validate(item, item_schema, f"{loc}[{i}]"))

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
'''

validator_path.write_text(validator_code, encoding="utf-8")

# 3. Strengthen Worker prompt
worker_prompt = Path(".agentic-pi/prompts/guarded_worker.md")
text = worker_prompt.read_text(encoding="utf-8-sig")

addition = """
Strict evidence rules:
- action_taken must not be empty.
- files_touched must list every file changed.
- evidence must not be empty.
- evidence must mention the created or modified artifact.
- If no file was changed, status must not be PASSED.
- Do not output placeholder empty arrays for files_touched or evidence.
"""

if "Strict evidence rules:" not in text:
    text = text.rstrip() + "\n\n" + addition.strip() + "\n"

worker_prompt.write_text(text, encoding="utf-8")

print("Hardened v0.1.1")
print("- step_result.schema.json rejects empty action_taken/files_touched/evidence")
print("- validate_schema.py supports minLength and minItems")
print("- guarded_worker.md has strict evidence rules")