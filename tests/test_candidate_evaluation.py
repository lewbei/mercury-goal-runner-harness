import json
import pathlib
import importlib.util
import sys

validator_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "validators" / "validate_candidate_evaluation.py"
spec = importlib.util.spec_from_file_location("validate_candidate_evaluation", validator_path)
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_candidate_evaluation"] = validator
spec.loader.exec_module(validator)
validate_candidate_evaluation = validator.validate_candidate_evaluation


def _minimal_candidate_evaluation_graph():
    """Return a minimal graph with a plan_candidate, its evaluation, and three checks."""
    return {
        "nodes": [
            {"id": "cand1", "type": "plan_candidate", "properties": {}},
            {"id": "eval1", "type": "candidate_evaluation", "properties": {}},
            {"id": "risk1", "type": "risk_check", "properties": {"result": "PASS"}},
            {"id": "tool1", "type": "tool_check", "properties": {"result": "PASS"}},
            {"id": "verify1", "type": "verify_check", "properties": {"result": "PASS"}}
        ],
        "edges": [
            {"source": "cand1", "target": "eval1", "type": "evaluated_by"},
            {"source": "eval1", "target": "risk1", "type": "checks_risk"},
            {"source": "eval1", "target": "tool1", "type": "checks_tool"},
            {"source": "eval1", "target": "verify1", "type": "checks_verifiability"}
        ]
    }


def test_candidate_evaluation_graph(tmp_path):
    """Validate a minimal candidate_evaluation graph against its validator."""
    graph_path = tmp_path / "candidate_evaluation.json"
    graph_path.write_text(json.dumps(_minimal_candidate_evaluation_graph()), encoding="utf-8")
    errors = validate_candidate_evaluation(str(graph_path))
    assert not errors, f"Validator reported errors: {errors}"
