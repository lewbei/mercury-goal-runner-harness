import json
import pathlib
import importlib.util
import sys

# Ensure the ubiquitous language schema test module is importable (runs its top‑level code)
import test_ubiquitous_language_contract  # noqa: F401


def _minimal_valid_graph():
    """Return a minimal valid plan‑graph JSON structure for testing."""
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


def test_plan_graph_v1_schema(tmp_path):
    """Validate that a minimal graph conforms to the schema and passes the validator."""
    # Write the graph to a temporary file
    graph_path = tmp_path / "minimal_plan_graph.json"
    graph_path.write_text(json.dumps(_minimal_valid_graph()), encoding="utf-8")

    # Load the schema – we only check that it is well‑formed JSON
    schema_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "schemas" / "plan_graph_v1.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    assert isinstance(schema, dict), "Schema should be a JSON object"

    # Dynamically import the validator (the .agentic-pi directory is not a Python package)
    validator_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "validators" / "validate_plan_graph_v1.py"
    spec = importlib.util.spec_from_file_location("validate_plan_graph_v1", validator_path)
    validator = importlib.util.module_from_spec(spec)
    sys.modules["validate_plan_graph_v1"] = validator
    spec.loader.exec_module(validator)
    validate_plan_graph = validator.validate_plan_graph

    errors = validate_plan_graph(str(graph_path))
    assert not errors, f"Validator reported errors: {errors}"
