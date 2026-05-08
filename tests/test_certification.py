import json
import pathlib
import importlib.util
import sys

# Dynamically load the certification validator
validator_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "validators" / "validate_certification.py"
spec = importlib.util.spec_from_file_location("validate_certification", validator_path)
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_certification"] = validator
spec.loader.exec_module(validator)
validate_certification = validator.validate_certification


def _minimal_certification_graph():
    """Return a minimal, valid certification graph.

    Includes a policy_decision (status CERTIFIED_DONE) and a certification node referencing it.
    """
    return {
        "nodes": [
            {"id": "a1", "type": "artifact", "properties": {"path": "out.txt", "hash": "abc"}},
            {"id": "v1", "type": "verifier_artifact", "properties": {"target_artifact": "a1", "provenance_level": "P2", "strength": "certifying"}},
            {"id": "pd1", "type": "policy_decision", "properties": {"verifier_ids": ["v1"], "status": "CERTIFIED_DONE"}},
            {"id": "cert1", "type": "certification", "properties": {"policy_decision_id": "pd1", "status": "CERTIFIED_DONE", "final_status_path": "final_status.md", "certification_json_path": "certification.json"}}
        ],
        "edges": [
            {"source": "v1", "target": "a1", "type": "verifies"}
        ]
    }


def test_certification_graph(tmp_path):
    """Validate the minimal certification graph against its validator."""
    graph_path = tmp_path / "certification.json"
    graph_path.write_text(json.dumps(_minimal_certification_graph()), encoding="utf-8")
    errors = validate_certification(str(graph_path))
    assert not errors, f"Validator reported errors: {errors}"
