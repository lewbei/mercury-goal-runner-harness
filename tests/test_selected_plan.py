import json
import pathlib
import importlib.util
import sys

validator_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "validators" / "validate_selected_plan.py"
spec = importlib.util.spec_from_file_location("validate_selected_plan", validator_path)
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_selected_plan"] = validator
spec.loader.exec_module(validator)
validate_selected_plan = validator.validate_selected_plan


def _minimal_selected_plan_graph():
    """Return a minimal graph with an applicability_gate, a selected_plan, and a success_criteria."""
    return {
        "nodes": [
            {"id": "cand1", "type": "plan_candidate", "properties": {}},
            {"id": "gate1", "type": "applicability_gate", "properties": {}},
            {"id": "sel1", "type": "selected_plan", "properties": {"source_candidate_id": "cand1", "selection_reason": "best verifier path"}},
            {"id": "sc1", "type": "success_criteria", "properties": {}}
        ],
        "edges": [
            {"source": "gate1", "target": "sel1", "type": "selected_as"},
            {"source": "sel1", "target": "sc1", "type": "requires_success"}
        ]
    }


def test_selected_plan_graph(tmp_path):
    """Validate a minimal selected_plan graph against its validator."""
    graph_path = tmp_path / "selected_plan.json"
    graph_path.write_text(json.dumps(_minimal_selected_plan_graph()), encoding="utf-8")
    errors = validate_selected_plan(str(graph_path))
    assert not errors, f"Validator reported errors: {errors}"
