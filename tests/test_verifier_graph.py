import json
import pathlib
import importlib.util
import sys

# Dynamically load the verifier‑graph validator
validator_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "validators" / "validate_verifier_graph.py"
spec = importlib.util.spec_from_file_location("validate_verifier_graph", validator_path)
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_verifier_graph"] = validator
spec.loader.exec_module(validator)
validate_verifier_graph = validator.validate_verifier_graph


def _minimal_verifier_graph():
    """Return a minimal, valid verifier‑graph JSON structure.

    One artifact and one verifier that points to it.
    """
    return {
        "nodes": [
            {"id": "a1", "type": "artifact", "properties": {"path": "out.txt", "hash": "abc"}},
            {"id": "v1", "type": "verifier_artifact", "properties": {"target_artifact": "a1", "provenance_level": "P2", "strength": "certifying"}}
        ],
        "edges": [
            {"source": "v1", "target": "a1", "type": "verifies"}
        ]
    }


def test_verifier_graph(tmp_path):
    """Validate the minimal verifier‑graph against its validator."""
    graph_path = tmp_path / "verifier_graph.json"
    graph_path.write_text(json.dumps(_minimal_verifier_graph()), encoding="utf-8")
    errors = validate_verifier_graph(str(graph_path))
    assert not errors, f"Validator reported errors: {errors}"
