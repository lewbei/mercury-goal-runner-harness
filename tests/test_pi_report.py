import json
import pathlib
import importlib.util
import sys

# Dynamically load the pi_report validator
validator_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "validators" / "validate_pi_report.py"
spec = importlib.util.spec_from_file_location("validate_pi_report", validator_path)
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_pi_report"] = validator
spec.loader.exec_module(validator)
validate_pi_report = validator.validate_pi_report


def _minimal_pi_report_graph():
    """Return a minimal valid pi_report graph.

    certification -> pi_report.
    """
    return {
        "nodes": [
            {"id": "cert1", "type": "certification", "properties": {"policy_decision_id": "pd1", "status": "CERTIFIED_DONE", "final_status_path": "final_status.md", "certification_json_path": "cert.json"}},
            {"id": "rep1", "type": "pi_report", "properties": {}}
        ],
        "edges": [
            {"source": "cert1", "target": "rep1", "type": "reported_by"}
        ]
    }


def test_pi_report(tmp_path):
    """Validate the minimal pi_report graph against its validator."""
    graph_path = tmp_path / "pi_report.json"
    graph_path.write_text(json.dumps(_minimal_pi_report_graph()), encoding="utf-8")
    errors = validate_pi_report(str(graph_path))
    assert not errors, f"Validator reported errors: {errors}"
