import json
import pathlib
import importlib.util
import sys

# Dynamically load the local‑step‑plan validator
validator_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "validators" / "validate_local_step_plan.py"
spec = importlib.util.spec_from_file_location("validate_local_step_plan", validator_path)
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_local_step_plan"] = validator
spec.loader.exec_module(validator)
validate_local_step_plan = validator.validate_local_step_plan


def _minimal_local_step_graph():
    """Return a minimal valid local‑step‑plan graph.

    milestone_plan -> two local_step_plan nodes -> merged_plan.
    """
    return {
        "nodes": [
            {"id": "ms1", "type": "milestone_plan", "properties": {}},
            {"id": "ls1", "type": "local_step_plan", "properties": {}},
            {"id": "ls2", "type": "local_step_plan", "properties": {}},
            {"id": "mp1", "type": "merged_plan", "properties": {}}
        ],
        "edges": [
            {"source": "ms1", "target": "ls1", "type": "decomposes_to"},
            {"source": "ms1", "target": "ls2", "type": "decomposes_to"},
            {"source": "ls1", "target": "mp1", "type": "compiles_to"},
            {"source": "ls2", "target": "mp1", "type": "compiles_to"}
        ]
    }


def test_local_step_plan(tmp_path):
    """Validate the minimal local‑step‑plan graph against its validator."""
    graph_path = tmp_path / "local_step_plan.json"
    graph_path.write_text(json.dumps(_minimal_local_step_graph()), encoding="utf-8")
    errors = validate_local_step_plan(str(graph_path))
    assert not errors, f"Validator reported errors: {errors}"
