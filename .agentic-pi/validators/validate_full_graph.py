import json
import importlib.util
import sys
from pathlib import Path

# Helper to load a validator from a file path
def _load_validator(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def validate_full_graph(graph_path: str):
    """Run all sub‑validators on a Plan Graph v1 and aggregate errors.

    Returns a list of error strings (empty list = graph passes all checks).
    """
    path = Path(graph_path)
    if not path.is_file():
        return [f"File not found: {graph_path}"]

    # Load each validator module dynamically – they live under .agentic-pi/validators
    base_dir = Path(__file__).resolve().parents[2] / ".agentic-pi" / "validators"
    validators = {
        "plan_graph": _load_validator("validate_plan_graph_v1", base_dir / "validate_plan_graph_v1.py"),
        "goal_contract": _load_validator("validate_goal_contract", base_dir / "validate_goal_contract.py"),
        "plan_seed": _load_validator("validate_plan_seed", base_dir / "validate_plan_seed.py"),
        "plan_candidate": _load_validator("validate_plan_candidate", base_dir / "validate_plan_candidate.py"),
        "candidate_evaluation": _load_validator("validate_candidate_evaluation", base_dir / "validate_candidate_evaluation.py"),
        "applicability_gate": _load_validator("validate_applicability_gate", base_dir / "validate_applicability_gate.py"),
        "selected_plan": _load_validator("validate_selected_plan", base_dir / "validate_selected_plan.py"),
        "milestone": _load_validator("validate_milestone_plan", base_dir / "validate_milestone_plan.py"),
        "local_step": _load_validator("validate_local_step_plan", base_dir / "validate_local_step_plan.py"),
        "merged": _load_validator("validate_merged_plan", base_dir / "validate_merged_plan.py"),
        "task": _load_validator("validate_task_graph", base_dir / "validate_task_graph.py"),
        "artifact": _load_validator("validate_artifact_graph", base_dir / "validate_artifact_graph.py"),
        "verifier": _load_validator("validate_verifier_graph", base_dir / "validate_verifier_graph.py"),
        "policy": _load_validator("validate_policy_decision", base_dir / "validate_policy_decision.py"),
        "certification": _load_validator("validate_certification", base_dir / "validate_certification.py"),
        "pi_report": _load_validator("validate_pi_report", base_dir / "validate_pi_report.py")
    }

    # Run each validator and collect errors
    all_errors = []
    for name, mod in validators.items():
        # Determine the function name for each validator, handling special cases
        if name == "plan_graph":
            func = getattr(mod, "validate_plan_graph")
        elif name == "milestone":
            func = getattr(mod, "validate_milestone_plan")
        elif name == "local_step":
            func = getattr(mod, "validate_local_step_plan")
        elif name == "merged":
            func = getattr(mod, "validate_merged_plan")
        elif name == "task":
            func = getattr(mod, "validate_task_graph")
        elif name == "artifact":
            func = getattr(mod, "validate_artifact_graph")
        elif name == "verifier":
            func = getattr(mod, "validate_verifier_graph")
        elif name == "policy":
            func = getattr(mod, "validate_policy_decision")
        else:
            func = getattr(mod, f"validate_{name}")
        errors = func(str(graph_path))
        if errors:
            all_errors.append(f"[{name}] " + "; ".join(errors))
    return all_errors
