import json
import pathlib
import importlib.util
import sys

# Dynamically load the task‑graph validator (the .agentic-pi directory is not a package)
validator_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "validators" / "validate_task_graph.py"
spec = importlib.util.spec_from_file_location("validate_task_graph", validator_path)
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_task_graph"] = validator
spec.loader.exec_module(validator)
validate_task_graph = validator.validate_task_graph


def _minimal_task_graph():
    """Return a minimal, valid task‑graph JSON structure.

    Two tasks (t1, t2) where t2 depends on t1, each produces an artifact.
    """
    return {
        "nodes": [
            {"id": "t1", "type": "task", "properties": {"task_id": "t1", "action": "run", "expected_artifact": "a1"}},
            {"id": "t2", "type": "task", "properties": {"task_id": "t2", "action": "run", "expected_artifact": "a2"}},
            {"id": "a1", "type": "artifact", "properties": {"path": "output1.txt", "hash": "abc123"}},
            {"id": "a2", "type": "artifact", "properties": {"path": "output2.txt", "hash": "def456"}}
        ],
        "edges": [
            {"source": "t1", "target": "a1", "type": "produces"},
            {"source": "t2", "target": "a2", "type": "produces"},
            {"source": "t2", "target": "t1", "type": "requires"}
        ]
    }


def test_task_graph(tmp_path):
    """Validate the minimal task‑graph against the validator."""
    graph_path = tmp_path / "task_graph.json"
    graph_path.write_text(json.dumps(_minimal_task_graph()), encoding="utf-8")
    errors = validate_task_graph(str(graph_path))
    assert not errors, f"Validator reported errors: {errors}"
