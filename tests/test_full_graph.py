import json
import pathlib
import importlib.util
import sys

# Dynamically load the full‑graph validator
validator_path = pathlib.Path(__file__).resolve().parents[1] / ".agentic-pi" / "validators" / "validate_full_graph.py"
spec = importlib.util.spec_from_file_location("validate_full_graph", validator_path)
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_full_graph"] = validator
spec.loader.exec_module(validator)
validate_full_graph = validator.validate_full_graph


def _minimal_full_graph():
    """Return a minimal, fully‑connected graph that satisfies all validators."""
    return {
        "nodes": [
            # Core contract
            {"id": "g1", "type": "raw_goal", "properties": {}},
            {"id": "c1", "type": "goal_contract", "properties": {}},
            {"id": "con1", "type": "constraint", "properties": {}},
            {"id": "sc1", "type": "success_criteria", "properties": {}},
            # Seed & candidates
            {"id": "ps1", "type": "plan_seed", "properties": {}},
            {"id": "cand1", "type": "plan_candidate", "properties": {"expected_outputs": ["a1"], "verifier_path": "v1.json", "tool_requirements": ["tool_x"], "risk_notes": "low"}},
            {"id": "cand2", "type": "plan_candidate", "properties": {"expected_outputs": ["a2"], "verifier_path": "v2.json", "tool_requirements": ["tool_y"], "risk_notes": "medium", "rejection_reason": "higher cost"}},
            # Candidate evaluations & checks
            {"id": "eval1", "type": "candidate_evaluation", "properties": {}},
            {"id": "eval2", "type": "candidate_evaluation", "properties": {}},
            {"id": "risk1", "type": "risk_check", "properties": {"result": "PASS"}},
            {"id": "risk2", "type": "risk_check", "properties": {"result": "PASS"}},
            {"id": "tool1", "type": "tool_check", "properties": {"result": "PASS"}},
            {"id": "tool2", "type": "tool_check", "properties": {"result": "PASS"}},
            {"id": "verify1", "type": "verify_check", "properties": {"result": "PASS"}},
            {"id": "verify2", "type": "verify_check", "properties": {"result": "PASS"}},
            # Applicability gate & selected plan
            {"id": "gate1", "type": "applicability_gate", "properties": {}},
            {"id": "sel1", "type": "selected_plan", "properties": {"source_candidate_id": "cand1", "selection_reason": "best verifier path"}},
            # Milestone & local steps
            {"id": "ms1", "type": "milestone_plan", "properties": {}},
            {"id": "ls1", "type": "local_step_plan", "properties": {}},
            {"id": "ls2", "type": "local_step_plan", "properties": {}},
            # Merged plan & tasks
            {"id": "mp1", "type": "merged_plan", "properties": {}},
            {"id": "t1", "type": "task", "properties": {"task_id": "t1", "action": "run", "expected_artifact": "a1"}},
            {"id": "t2", "type": "task", "properties": {"task_id": "t2", "action": "run", "expected_artifact": "a2"}},
            # Artifacts
            {"id": "a1", "type": "artifact", "properties": {"path": "out1.txt", "hash": "abc"}},
            {"id": "a2", "type": "artifact", "properties": {"path": "out2.txt", "hash": "def"}},
            # Verifier artifacts
            {"id": "v1", "type": "verifier_artifact", "properties": {"target_artifact": "a1", "provenance_level": "P2", "strength": "certifying"}},
            {"id": "v2", "type": "verifier_artifact", "properties": {"target_artifact": "a2", "provenance_level": "P2", "strength": "certifying"}},
            # Policy decision
            {"id": "pd1", "type": "policy_decision", "properties": {"verifier_ids": ["v1", "v2"], "status": "CERTIFIED_DONE"}},
            # Certification
            {"id": "cert1", "type": "certification", "properties": {"policy_decision_id": "pd1", "status": "CERTIFIED_DONE", "final_status_path": "final_status.md", "certification_json_path": "cert.json"}},
            # Pi report
            {"id": "rep1", "type": "pi_report", "properties": {}}
        ],
        "edges": [
            # Goal contract
            {"source": "g1", "target": "c1", "type": "defines"},
            {"source": "c1", "target": "con1", "type": "constrains"},
            {"source": "c1", "target": "sc1", "type": "requires_success"},
            {"source": "c1", "target": "ps1", "type": "generates_seed"},
            # Seed → candidates
            {"source": "ps1", "target": "cand1", "type": "expands_to_candidate"},
            {"source": "ps1", "target": "cand2", "type": "expands_to_candidate"},
            # Candidates → evaluations
            {"source": "cand1", "target": "eval1", "type": "evaluated_by"},
            {"source": "cand2", "target": "eval2", "type": "evaluated_by"},
            # Evaluations → checks
            {"source": "eval1", "target": "risk1", "type": "checks_risk"},
            {"source": "eval1", "target": "tool1", "type": "checks_tool"},
            {"source": "eval1", "target": "verify1", "type": "checks_verifiability"},
            {"source": "eval2", "target": "risk2", "type": "checks_risk"},
            {"source": "eval2", "target": "tool2", "type": "checks_tool"},
            {"source": "eval2", "target": "verify2", "type": "checks_verifiability"},
            # Evaluations → applicability gate
            {"source": "eval1", "target": "gate1", "type": "evaluated_by"},
            {"source": "eval2", "target": "gate1", "type": "evaluated_by"},
            # Gate → selected plan
            {"source": "gate1", "target": "sel1", "type": "selected_as"},
            # Optional rejection edges (showing that a candidate can be rejected)
            {"source": "gate1", "target": "cand2", "type": "rejected_by", "properties": {"reason": "higher cost"}},
            # Selected plan → success criteria
            {"source": "sel1", "target": "sc1", "type": "requires_success"},
            # Selected plan → milestone
            {"source": "sel1", "target": "ms1", "type": "decomposes_to"},
            # Milestone → local steps
            {"source": "ms1", "target": "ls1", "type": "decomposes_to"},
            {"source": "ms1", "target": "ls2", "type": "decomposes_to"},
            # Local steps → merged plan
            {"source": "ls1", "target": "mp1", "type": "compiles_to"},
            {"source": "ls2", "target": "mp1", "type": "compiles_to"},
            # Merged plan → tasks
            {"source": "mp1", "target": "t1", "type": "decomposes_to"},
            {"source": "mp1", "target": "t2", "type": "decomposes_to"},
            # Tasks → artifacts
            {"source": "t1", "target": "a1", "type": "produces"},
            {"source": "t2", "target": "a2", "type": "produces"},
            # Verifier artifacts → artifacts
            {"source": "v1", "target": "a1", "type": "verifies"},
            {"source": "v2", "target": "a2", "type": "verifies"},
            # Certification → pi_report
            {"source": "cert1", "target": "rep1", "type": "reported_by"}
        ]
    }


def test_full_graph(tmp_path):
    """Validate the minimal full graph against the aggregate validator."""
    graph_path = tmp_path / "full_graph.json"
    graph_path.write_text(json.dumps(_minimal_full_graph()), encoding="utf-8")
    errors = validate_full_graph(str(graph_path))
    assert not errors, f"Full graph validation failed: {errors}"
