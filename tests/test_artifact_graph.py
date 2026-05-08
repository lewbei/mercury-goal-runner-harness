import json
import pathlib
import importlib.util
import sys

# Dynamically load the artifact‑graph validator
validator_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "validators" / "validate_artifact_graph.py"
spec = importlib.util.spec_from_file_location("validate_artifact_graph", validator_path)
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_artifact_graph"] = validator
spec.loader.exec_module(validator)
validate_artifact_graph = validator.validate_artifact_graph


def _minimal_artifact_graph():
    """Return a minimal, valid artifact‑graph JSON structure.

    Two tasks each producing a distinct artifact.
    """
    return {
        "nodes": [
            {"id": "t1", "type": "task", "properties": {"task_id": "t1", "action": "run", "expected_artifact": "a1"}},
            {"id": "t2", "type": "task", "properties": {"task_id": "t2", "action": "run", "expected_artifact": "a2"}},
            {"id": "a1", "type": "artifact", "properties": {"path": "out1.txt", "hash": "abc"}},
            {"id": "a2", "type": "artifact", "properties": {"path": "out2.txt", "hash": "def"}}
        ],
        "edges": [
            {"source": "t1", "target": "a1", "type": "produces"},
            {"source": "t2", "target": "a2", "type": "produces"}
        ]
    }


def test_artifact_graph(tmp_path):
    """Validate the minimal artifact‑graph against its validator."""
    graph_path = tmp_path / "artifact_graph.json"
    graph_path.write_text(json.dumps(_minimal_artifact_graph()), encoding="utf-8")
    errors = validate_artifact_graph(str(graph_path))
    assert not errors, f"Validator reported errors: {errors}"
