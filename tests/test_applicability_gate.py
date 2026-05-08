import json
import pathlib
import importlib.util
import sys

validator_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "validators" / "validate_applicability_gate.py"
spec = importlib.util.spec_from_file_location("validate_applicability_gate", validator_path)
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_applicability_gate"] = validator
spec.loader.exec_module(validator)
validate_applicability_gate = validator.validate_applicability_gate


def _minimal_applicability_gate_graph():
    """Return a minimal graph with a candidate_evaluation, an applicability_gate, a selected_plan, and a rejected plan."""
    return {
        "nodes": [
            {"id": "cand1", "type": "plan_candidate", "properties": {}},
            {"id": "eval1", "type": "candidate_evaluation", "properties": {}},
            {"id": "gate1", "type": "applicability_gate", "properties": {}},
            {"id": "sel1", "type": "selected_plan", "properties": {"source_candidate_id": "cand1", "selection_reason": "best verifier path"}},
            {"id": "rej1", "type": "plan_candidate", "properties": {"rejection_reason": "weaker verifier path"}}
        ],
        "edges": [
            {"source": "cand1", "target": "eval1", "type": "evaluated_by"},
            {"source": "eval1", "target": "gate1", "type": "evaluated_by"},
            {"source": "gate1", "target": "sel1", "type": "selected_as"},
            {"source": "gate1", "target": "rej1", "type": "rejected_by", "properties": {"reason": "weaker verifier path"}}
        ]
    }


def test_applicability_gate_graph(tmp_path):
    """Validate a minimal applicability_gate graph against its validator."""
    graph_path = tmp_path / "applicability_gate.json"
    graph_path.write_text(json.dumps(_minimal_applicability_gate_graph()), encoding="utf-8")
    errors = validate_applicability_gate(str(graph_path))
    assert not errors, f"Validator reported errors: {errors}"
