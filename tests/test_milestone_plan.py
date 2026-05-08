import json
import pathlib
import importlib.util
import sys

# Dynamically load the milestone‑plan validator
validator_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "validators" / "validate_milestone_plan.py"
spec = importlib.util.spec_from_file_location("validate_milestone_plan", validator_path)
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_milestone_plan"] = validator
spec.loader.exec_module(validator)
validate_milestone_plan = validator.validate_milestone_plan


def _minimal_milestone_graph():
    """Return a minimal valid milestone‑plan graph.

    selected_plan -> milestone_plan -> two local_step_plan nodes.
    """
    return {
        "nodes": [
            {"id": "sel1", "type": "selected_plan", "properties": {}},
            {"id": "ms1", "type": "milestone_plan", "properties": {}},
            {"id": "ls1", "type": "local_step_plan", "properties": {}},
            {"id": "ls2", "type": "local_step_plan", "properties": {}}
        ],
        "edges": [
            {"source": "sel1", "target": "ms1", "type": "decomposes_to"},
            {"source": "ms1", "target": "ls1", "type": "decomposes_to"},
            {"source": "ms1", "target": "ls2", "type": "decomposes_to"}
        ]
    }


def test_milestone_plan(tmp_path):
    """Validate the minimal milestone‑plan graph against its validator."""
    graph_path = tmp_path / "milestone_plan.json"
    graph_path.write_text(json.dumps(_minimal_milestone_graph()), encoding="utf-8")
    errors = validate_milestone_plan(str(graph_path))
    assert not errors, f"Validator reported errors: {errors}"
