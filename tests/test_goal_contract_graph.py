import json
import pathlib
import importlib.util
import sys

# Load the validator dynamically (the .agentic-pi directory is not a package)
validator_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "validators" / "validate_goal_contract.py"
spec = importlib.util.spec_from_file_location("validate_goal_contract", validator_path)
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_goal_contract"] = validator
spec.loader.exec_module(validator)
validate_goal_contract = validator.validate_goal_contract


def _minimal_goal_contract():
    """Return a minimal valid goal‑contract graph JSON structure."""
    return {
        "nodes": [
            {"id": "g1", "type": "raw_goal", "properties": {}},
            {"id": "c1", "type": "goal_contract", "properties": {}},
            {"id": "con1", "type": "constraint", "properties": {}},
            {"id": "sc1", "type": "success_criteria", "properties": {}},
            {"id": "ps1", "type": "plan_seed", "properties": {}}
        ],
        "edges": [
            {"source": "g1", "target": "c1", "type": "defines"},
            {"source": "c1", "target": "con1", "type": "constrains"},
            {"source": "c1", "target": "sc1", "type": "requires_success"},
            {"source": "c1", "target": "ps1", "type": "generates_seed"}
        ]
    }


def test_goal_contract_graph(tmp_path):
    """Validate a minimal goal‑contract graph against its schema and validator."""
    graph_path = tmp_path / "goal_contract.json"
    graph_path.write_text(json.dumps(_minimal_goal_contract()), encoding="utf-8")

    # Load the schema to ensure it is valid JSON (no further validation performed here)
    schema_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "schemas" / "goal_contract.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    assert isinstance(schema, dict), "Schema should be a JSON object"

    errors = validate_goal_contract(str(graph_path))
    assert not errors, f"Validator reported errors: {errors}"
