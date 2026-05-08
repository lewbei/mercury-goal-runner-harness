import json
import pathlib
import importlib.util
import sys

validator_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "validators" / "validate_plan_candidate.py"
spec = importlib.util.spec_from_file_location("validate_plan_candidate", validator_path)
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_plan_candidate"] = validator
spec.loader.exec_module(validator)
validate_plan_candidate = validator.validate_plan_candidate


def _minimal_plan_candidate_graph():
    """Return a minimal graph with a plan_seed and two plan_candidate nodes, each with required properties."""
    return {
        "nodes": [
            {"id": "ps1", "type": "plan_seed", "properties": {}},
            {
                "id": "cand1",
                "type": "plan_candidate",
                "properties": {
                    "expected_outputs": ["out1"],
                    "verifier_path": "verifier_a.json",
                    "tool_requirements": ["tool_x"],
                    "risk_notes": "low"
                }
            },
            {
                "id": "cand2",
                "type": "plan_candidate",
                "properties": {
                    "expected_outputs": ["out2"],
                    "verifier_path": "verifier_b.json",
                    "tool_requirements": ["tool_y"],
                    "risk_notes": "medium"
                }
            }
        ],
        "edges": [
            {"source": "ps1", "target": "cand1", "type": "expands_to_candidate"},
            {"source": "ps1", "target": "cand2", "type": "expands_to_candidate"}
        ]
    }


def test_plan_candidate_graph(tmp_path):
    """Validate a minimal plan_candidate graph against its validator."""
    graph_path = tmp_path / "plan_candidate.json"
    graph_path.write_text(json.dumps(_minimal_plan_candidate_graph()), encoding="utf-8")
    errors = validate_plan_candidate(str(graph_path))
    assert not errors, f"Validator reported errors: {errors}"
