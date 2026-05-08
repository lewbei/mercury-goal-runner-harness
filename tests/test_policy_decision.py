import json
import pathlib
import importlib.util
import sys

# Dynamically load the policy decision validator
validator_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "validators" / "validate_policy_decision.py"
spec = importlib.util.spec_from_file_location("validate_policy_decision", validator_path)
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_policy_decision"] = validator
spec.loader.exec_module(validator)
validate_policy_decision = validator.validate_policy_decision


def _minimal_policy_decision_graph():
    """Return a minimal, valid policy decision graph.

    One verifier_artifact (P2, certifying) and a policy_decision referencing it with status CERTIFIED_DONE.
    """
    return {
        "nodes": [
            {"id": "a1", "type": "artifact", "properties": {"path": "out.txt", "hash": "abc"}},
            {"id": "v1", "type": "verifier_artifact", "properties": {"target_artifact": "a1", "provenance_level": "P2", "strength": "certifying"}},
            {"id": "pd1", "type": "policy_decision", "properties": {"verifier_ids": ["v1"], "status": "CERTIFIED_DONE"}}
        ],
        "edges": [
            {"source": "v1", "target": "a1", "type": "verifies"}
        ]
    }


def test_policy_decision_graph(tmp_path):
    """Validate the minimal policy decision graph against its validator."""
    graph_path = tmp_path / "policy_decision.json"
    graph_path.write_text(json.dumps(_minimal_policy_decision_graph()), encoding="utf-8")
    errors = validate_policy_decision(str(graph_path))
    assert not errors, f"Validator reported errors: {errors}"
