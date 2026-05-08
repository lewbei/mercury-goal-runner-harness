import json
import pathlib
import importlib.util
import sys

# Dynamically load the merged‑plan validator
validator_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "validators" / "validate_merged_plan.py"
spec = importlib.util.spec_from_file_location("validate_merged_plan", validator_path)
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_merged_plan"] = validator
spec.loader.exec_module(validator)
validate_merged_plan = validator.validate_merged_plan


def _minimal_merged_plan_graph():
    """Return a minimal valid merged‑plan graph.

    Two local_step_plan nodes -> merged_plan -> two task nodes.
    """
    return {
        "nodes": [
            {"id": "ls1", "type": "local_step_plan", "properties": {}},
            {"id": "ls2", "type": "local_step_plan", "properties": {}},
            {"id": "mp1", "type": "merged_plan", "properties": {}},
            {"id": "t1", "type": "task", "properties": {"task_id": "t1", "action": "run", "expected_artifact": "a1"}},
            {"id": "t2", "type": "task", "properties": {"task_id": "t2", "action": "run", "expected_artifact": "a2"}}
        ],
        "edges": [
            {"source": "ls1", "target": "mp1", "type": "compiles_to"},
            {"source": "ls2", "target": "mp1", "type": "compiles_to"},
            {"source": "mp1", "target": "t1", "type": "decomposes_to"},
            {"source": "mp1", "target": "t2", "type": "decomposes_to"}
        ]
    }


def test_merged_plan(tmp_path):
    """Validate the minimal merged‑plan graph against its validator."""
    graph_path = tmp_path / "merged_plan.json"
    graph_path.write_text(json.dumps(_minimal_merged_plan_graph()), encoding="utf-8")
    errors = validate_merged_plan(str(graph_path))
    assert not errors, f"Validator reported errors: {errors}"
