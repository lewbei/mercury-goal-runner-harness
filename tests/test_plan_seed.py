import json
import pathlib
import importlib.util
import sys

# Load the validator dynamically (the .agentic-pi directory is not a package)
validator_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "validators" / "validate_plan_seed.py"
spec = importlib.util.spec_from_file_location("validate_plan_seed", validator_path)
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_plan_seed"] = validator
spec.loader.exec_module(validator)
validate_plan_seed = validator.validate_plan_seed


def _minimal_plan_seed_graph():
    """Return a minimal valid graph containing a plan_seed and required edges."""
    return {
        "nodes": [
            {"id": "g1", "type": "raw_goal", "properties": {}},
            {"id": "c1", "type": "goal_contract", "properties": {}},
            {"id": "con1", "type": "constraint", "properties": {}},
            {"id": "sc1", "type": "success_criteria", "properties": {}},
            {"id": "ps1", "type": "plan_seed", "properties": {}},
            {"id": "cand1", "type": "plan_candidate", "properties": {}}
        ],
        "edges": [
            {"source": "g1", "target": "c1", "type": "defines"},
            {"source": "c1", "target": "con1", "type": "constrains"},
            {"source": "c1", "target": "sc1", "type": "requires_success"},
            {"source": "c1", "target": "ps1", "type": "generates_seed"},
            {"source": "ps1", "target": "cand1", "type": "expands_to_candidate"}
        ]
    }


def test_plan_seed_graph(tmp_path):
    """Validate a minimal plan_seed graph against its validator."""
    graph_path = tmp_path / "plan_seed.json"
    graph_path.write_text(json.dumps(_minimal_plan_seed_graph()), encoding="utf-8")
    errors = validate_plan_seed(str(graph_path))
    assert not errors, f"Validator reported errors: {errors}"
