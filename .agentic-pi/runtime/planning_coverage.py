#!/usr/bin/env python3
"""Build run-local planning coverage evidence without certifying DONE.

The artifact answers a narrow question: what did the planner explicitly cover,
what did it reject/defer, and where should verification catch mistakes? It does
not claim exhaustive planning and it never writes final status artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = ROOT / ".agentic-runs"
STATUS_ARTIFACTS = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}

RESEARCH_BASIS = [
    {
        "source_title": "Large Language Models for Planning: A Comprehensive and Systematic Survey",
        "source_url": "https://arxiv.org/html/2505.19683v1",
        "applied_lesson": "Planning should record decomposition, search/exploration choices, constraints, and verifier handoff rather than claiming exhaustive reasoning.",
    },
    {
        "source_title": "Demystifying Chains, Trees, and Graphs of Thoughts",
        "source_url": "https://arxiv.org/html/2401.14295v6",
        "applied_lesson": "Branching/tree/graph reasoning improves coverage by making alternatives explicit and scorable, but still remains bounded search.",
    },
    {
        "source_title": "PlanGenLLMs: A Modern Survey of LLM Planning Capabilities",
        "source_url": "https://aclanthology.org/2025.acl-long.958.pdf",
        "applied_lesson": "Planning quality should be checked with constraint adherence, plan rationality, verifier-guided selection, and failure-aware evaluation.",
    },
    {
        "source_title": "Tree-of-Thoughts reference implementation",
        "source_url": "https://github.com/princeton-nlp/tree-of-thought-llm",
        "applied_lesson": "Expose generate/evaluate/select frontier bookkeeping, but keep LLM voting outside the certifier boundary.",
    },
    {
        "source_title": "Graph-of-Thoughts reference implementation",
        "source_url": "https://github.com/spcl/graph-of-thoughts",
        "applied_lesson": "Represent planning operations and dependencies as inspectable graph evidence rather than opaque confidence.",
    },
    {
        "source_title": "Language Agent Tree Search reference implementation",
        "source_url": "https://github.com/lapisrocks/LanguageAgentTreeSearch",
        "applied_lesson": "Selection, expansion, evaluation, rollout, backpropagation, and failed-trajectory reflection are useful audit concepts, but rollout rewards cannot certify DONE.",
    },
]

SOURCE_ARTIFACTS = [
    ("goal_contract.json", True),
    ("task_type_decision.json", False),
    ("domain_pack_selection.json", False),
    ("capability_inventory.json", False),
    ("strategy_candidates.json", True),
    ("strategy_applicability.json", True),
    ("retrieved_experience.json", False),
    ("adaptive_research_inputs.json", False),
    ("strategy_scores.json", True),
    ("strategy_decision.json", True),
    ("planning_search_tree.json", False),
    ("selected_strategy.json", False),
    ("rejected_strategies.json", False),
    ("milestone_plan.json", False),
    ("local_step_plan.json", False),
    ("expected_artifacts.json", False),
    ("merged_plan.json", False),
    ("plan_graph.json", False),
]


class PlanningCoverageError(RuntimeError):
    """Raised when coverage cannot be built safely."""


def load_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_run_dir(raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        run_dir = candidate
    elif candidate.parts and candidate.parts[0] == ".agentic-runs":
        run_dir = ROOT / candidate
    else:
        run_dir = RUNS_ROOT / raw
    run_dir = run_dir.resolve()
    runs_root = RUNS_ROOT.resolve()
    if run_dir != runs_root and runs_root not in run_dir.parents:
        raise PlanningCoverageError(f"run directory must be under .agentic-runs: {raw}")
    if not run_dir.is_dir():
        raise PlanningCoverageError(f"run directory missing: {raw}")
    return run_dir


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def unique(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def source_artifacts(run_dir: Path) -> list[dict[str, Any]]:
    return [
        {"path": rel_path, "required": required, "exists": (run_dir / rel_path).is_file()}
        for rel_path, required in SOURCE_ARTIFACTS
    ]


def selected_strategy_id(decision: dict, selected: dict) -> str:
    return str(decision.get("selected_strategy") or selected.get("strategy_id") or "").strip()


def build_alternatives(run_dir: Path, candidates_doc: dict, decision: dict, selected: dict) -> list[dict[str, Any]]:
    selected_id = selected_strategy_id(decision, selected)
    candidates = candidates_doc.get("candidates", []) if isinstance(candidates_doc, dict) else []
    candidate_by_id = {
        str(candidate.get("strategy_id", "")): candidate
        for candidate in candidates
        if isinstance(candidate, dict) and candidate.get("strategy_id")
    }
    alternatives: list[dict[str, Any]] = []

    if selected_id:
        selected_candidate = candidate_by_id.get(selected_id, selected if selected else {})
        alternatives.append({
            "option_id": selected_id,
            "source": "strategy_decision.json",
            "status": "selected",
            "reason": str(decision.get("reason") or "Selected by deterministic strategy scoring and applicability checks."),
            "evidence_refs": ["strategy_scores.json", "strategy_decision.json", "selected_strategy.json"],
            "verifier_path": "; ".join(as_list(selected_candidate.get("verifier_requirements"))) or "Verifier requirements must be supplied before certification.",
        })

    rejected_doc = load_json(run_dir / "rejected_strategies.json", {}) or {}
    rejected = decision.get("rejected_strategies") or rejected_doc.get("rejected_strategies") or []
    for item in rejected:
        if not isinstance(item, dict):
            continue
        strategy_id = str(item.get("strategy_id") or "").strip()
        if not strategy_id or strategy_id == selected_id:
            continue
        candidate = candidate_by_id.get(strategy_id, {})
        alternatives.append({
            "option_id": strategy_id,
            "source": "rejected_strategies.json",
            "status": "rejected",
            "reason": str(item.get("reason") or "Not selected by deterministic strategy ordering."),
            "evidence_refs": ["strategy_candidates.json", "strategy_scores.json", "rejected_strategies.json"],
            "verifier_path": "; ".join(as_list(candidate.get("verifier_requirements"))) or "Rejected strategy did not provide a stronger verifier path.",
        })

    applicability = load_json(run_dir / "strategy_applicability.json", {}) or {}
    for item in applicability.get("blocked_strategies", []):
        if not isinstance(item, dict):
            continue
        strategy_id = str(item.get("strategy_id") or "").strip()
        if not strategy_id or strategy_id == selected_id:
            continue
        alternatives.append({
            "option_id": strategy_id,
            "source": "strategy_applicability.json",
            "status": "blocked",
            "reason": "; ".join(as_list(item.get("block_reasons"))) or "Blocked by applicability gate.",
            "evidence_refs": ["strategy_applicability.json"],
            "verifier_path": "Blocked strategies cannot reach verifier handoff until gate failures are repaired.",
        })

    if decision.get("decision_status") == "NEED_USER_STRATEGY":
        alternatives.append({
            "option_id": "A.NEED_USER_STRATEGY",
            "source": "strategy_decision.json",
            "status": "need_user",
            "reason": str(decision.get("reason") or "No safe executable strategy was selected."),
            "evidence_refs": ["strategy_decision.json"],
            "verifier_path": "User must classify the task or provide verifier direction before execution.",
        })

    # Research-guided deferred branches. These are not fake executed branches; they
    # document bounded search limits and where a higher-cost planner could expand.
    adaptive_research = load_json(run_dir / "adaptive_research_inputs.json", {}) or {}
    if adaptive_research and not any(item["option_id"] == "A.ADAPTIVE_RESEARCH_INPUTS" for item in alternatives):
        alternatives.append({
            "option_id": "A.ADAPTIVE_RESEARCH_INPUTS",
            "source": "adaptive_research_inputs.json",
            "status": "deferred",
            "reason": "Adaptive/autoresearch findings can refine planning questions and verifier follow-up, but remain planning-only and non-certifying.",
            "evidence_refs": ["adaptive_research_inputs.json"],
            "verifier_path": "Validate adaptive_research_inputs.json, then require independent verifier artifacts before policy/certifier status.",
        })
    if not any(item["option_id"] == "A.EXPANDED_TREE_OR_GRAPH_SEARCH" for item in alternatives):
        alternatives.append({
            "option_id": "A.EXPANDED_TREE_OR_GRAPH_SEARCH",
            "source": "research_basis",
            "status": "deferred",
            "reason": "Tree/graph/MCTS-style expansion can explore more branches, but this run used bounded deterministic strategy selection.",
            "evidence_refs": ["planning_coverage.json", "strategy_candidates.json"],
            "verifier_path": "Use only as extra planning evidence; selected branch still needs verifier artifacts and certifier policy.",
        })
    if not any(item["option_id"] == "A.ASK_USER_OR_DEFER" for item in alternatives):
        alternatives.append({
            "option_id": "A.ASK_USER_OR_DEFER",
            "source": "goal_contract.json",
            "status": "deferred",
            "reason": "If constraints, verifier path, or output ownership become ambiguous, stop and ask instead of inventing coverage.",
            "evidence_refs": ["goal_contract.json"],
            "verifier_path": "User clarification is not verifier evidence; certification still belongs to policy/certifier artifacts.",
        })
    return alternatives


def build_assumptions(goal: dict, selected: dict) -> list[dict[str, str]]:
    assumptions = []
    for item in as_list(goal.get("inferred_constraints")):
        assumptions.append({
            "assumption": item,
            "source": "goal_contract.inferred_constraints",
            "validation_or_escape": "Verifier or user review must catch a bad inference before certification.",
        })
    if selected:
        assumptions.append({
            "assumption": f"Selected strategy {selected.get('strategy_id', '')} is the best bounded deterministic strategy, not the only possible plan.",
            "source": "selected_strategy.json",
            "validation_or_escape": "Rejected/deferred alternatives remain visible in planning_coverage.json.",
        })
    if not assumptions:
        assumptions.append({
            "assumption": "goal_contract.json is the authoritative planning input for this run.",
            "source": "goal_contract.json",
            "validation_or_escape": "Stop and ask the user if the goal contract omits critical constraints.",
        })
    return assumptions


def build_risk_register(goal: dict, selected: dict, candidates_doc: dict, adaptive_research: dict | None = None) -> list[dict[str, str]]:
    risks = []
    raw_risks = []
    raw_risks.extend(as_list(selected.get("risk_notes") if isinstance(selected, dict) else []))
    for candidate in candidates_doc.get("candidates", []) if isinstance(candidates_doc, dict) else []:
        if isinstance(candidate, dict):
            raw_risks.extend(as_list(candidate.get("risk_notes")))
    raw_risks.extend(as_list(goal.get("failure_criteria")))
    for finding in (adaptive_research or {}).get("findings", []):
        if isinstance(finding, dict):
            raw_risks.append(
                f"Adaptive research finding {finding.get('finding_id', 'unknown')} is advisory only: {finding.get('limitations', 'requires verifier follow-up')}"
            )
    raw_risks.extend([
        "Planner may miss a better branch because planning search is bounded.",
        "Artifact existence can look successful while behavior or evidence is wrong.",
    ])
    for index, risk in enumerate(unique(raw_risks), start=1):
        risks.append({
            "risk_id": f"R{index:03d}",
            "risk": risk,
            "mitigation": "Keep this as planning evidence only; require verifier artifacts and certifier policy before final status.",
            "source": "goal/strategy/planning_coverage",
        })
    return risks


def expected_artifact_paths(expected_doc: dict, selected: dict, goal: dict) -> list[str]:
    paths = []
    if isinstance(expected_doc, dict):
        for item in expected_doc.get("artifacts", []):
            if isinstance(item, dict):
                paths.extend(as_list(item.get("expected_path")))
    paths.extend(as_list(selected.get("expected_artifacts") if isinstance(selected, dict) else []))
    paths.extend(as_list(goal.get("final_outputs")))
    return unique(paths) or ["artifacts/output.txt"]


def build_false_done_traps(goal: dict) -> list[dict[str, str]]:
    traps = [
        {
            "trap": "Planner created a plausible plan but worker/verifier/certifier did not complete.",
            "mitigation": "roadmap/planning artifacts cannot set final status; run verifier and certifier-owned policy.",
        },
        {
            "trap": "Required file exists but does not satisfy the user's done criteria.",
            "mitigation": "Verifier artifacts must check behavior or content against done_criteria, not only existence.",
        },
        {
            "trap": "Selected branch passed scoring while an unexpanded branch could be safer.",
            "mitigation": "Record deferred search and ask-user triggers; do not claim exhaustive planning.",
        },
    ]
    for item in as_list(goal.get("forbidden_actions")):
        traps.append({
            "trap": item,
            "mitigation": "Forbidden actions stay visible to worker, verifier, policy, and certifier gates.",
        })
    return traps


def build_ask_user_triggers(goal: dict, decision: dict) -> list[dict[str, str]]:
    triggers = []
    for item in as_list(goal.get("ask_user_conditions")):
        triggers.append({
            "condition": item,
            "source": "goal_contract.ask_user_conditions",
            "required_when": "Before worker execution if the condition is true.",
        })
    for item in as_list(goal.get("ambiguities")):
        triggers.append({
            "condition": item,
            "source": "goal_contract.ambiguities",
            "required_when": "Before selecting or executing a branch that depends on this ambiguity.",
        })
    if decision.get("decision_status") == "NEED_USER_STRATEGY":
        triggers.append({
            "condition": str(decision.get("reason") or "No executable strategy selected."),
            "source": "strategy_decision.json",
            "required_when": "Immediately; execution should not continue without user strategy direction.",
        })
    if not triggers:
        triggers.append({
            "condition": "Any new ambiguity, missing verifier path, or output-path conflict appears during execution.",
            "source": "planning_coverage_default",
            "required_when": "Stop before inventing artifacts, verifier evidence, or final status.",
        })
    return triggers


def pass_check(check_id: str, passed: bool, evidence: str) -> dict[str, str]:
    return {"check_id": check_id, "status": "PASS" if passed else "FAIL", "evidence": evidence}


def build_coverage_checks(coverage: dict) -> list[dict[str, str]]:
    alternatives = coverage["alternatives_considered"]
    goal_coverage = coverage["goal_coverage"]
    authority = coverage["authority"]
    proof_boundary = coverage["proof_boundary"]
    checks = [
        pass_check(
            "C.AUTHORITY_BOUNDARY",
            authority.get("can_certify_done") is False and authority.get("final_status_authority") == "certifier_only",
            "Planning coverage is explicitly planning-only and certifier-owned final status is preserved.",
        ),
        pass_check(
            "C.CORRECTNESS_BOUNDARY",
            authority.get("claim_correctness") is False
            and proof_boundary.get("proves_artifact_correctness") is False
            and proof_boundary.get("requires_verifier_artifacts") is True
            and proof_boundary.get("requires_certifier") is True,
            "Planning coverage explicitly cannot prove artifact correctness; verifier artifacts and certifier policy remain required.",
        ),
        pass_check(
            "C.ALTERNATIVES_RECORDED",
            any(item.get("status") == "selected" for item in alternatives) and len(alternatives) >= 2,
            f"Recorded {len(alternatives)} selected/rejected/deferred/blocked alternatives.",
        ),
        pass_check(
            "C.REJECTED_OR_DEFERRED_RECORDED",
            any(item.get("status") in {"rejected", "deferred", "blocked", "need_user"} for item in alternatives),
            "At least one non-selected branch or stop condition is visible.",
        ),
        pass_check(
            "C.CONSTRAINTS_CAPTURED",
            bool(goal_coverage.get("constraints")) and bool(goal_coverage.get("done_criteria")) and bool(goal_coverage.get("failure_criteria")),
            "Goal constraints, done criteria, and failure criteria are copied into coverage.",
        ),
        pass_check(
            "C.RISKS_CAPTURED",
            bool(coverage.get("risk_register")),
            f"Recorded {len(coverage.get('risk_register', []))} planning risks.",
        ),
        pass_check(
            "C.VERIFIER_HANDOFF_RECORDED",
            bool(coverage.get("verification_strategy", {}).get("verifier_requirements"))
            and bool(coverage.get("verification_strategy", {}).get("expected_artifacts")),
            "Verifier requirements and expected artifacts are present.",
        ),
        pass_check(
            "C.FALSE_DONE_TRAPS_RECORDED",
            bool(coverage.get("false_done_traps")),
            "False-DONE traps are explicitly listed.",
        ),
        pass_check(
            "C.ASK_USER_TRIGGERS_RECORDED",
            bool(coverage.get("ask_user_triggers")),
            "Ask-user or stop conditions are explicitly listed.",
        ),
    ]
    return checks


def build_planning_coverage(run_dir: Path) -> dict[str, Any]:
    if any((run_dir / name).exists() for name in STATUS_ARTIFACTS):
        # This is not fatal: coverage may be inspected after certification. It is
        # still not authority and must not overwrite status artifacts.
        status_note = "status artifacts already exist; planning coverage remains non-authoritative"
    else:
        status_note = "status artifacts absent during coverage build"

    goal = load_json(run_dir / "goal_contract.json", {}) or {}
    candidates_doc = load_json(run_dir / "strategy_candidates.json", {}) or {}
    decision = load_json(run_dir / "strategy_decision.json", {}) or {}
    selected = load_json(run_dir / "selected_strategy.json", {}) or {}
    expected_doc = load_json(run_dir / "expected_artifacts.json", {}) or {}
    search_tree = load_json(run_dir / "planning_search_tree.json", {}) or {}
    adaptive_research = load_json(run_dir / "adaptive_research_inputs.json", {}) or {}

    if not goal:
        raise PlanningCoverageError("goal_contract.json is required")
    if not candidates_doc:
        raise PlanningCoverageError("strategy_candidates.json is required")
    if not decision:
        raise PlanningCoverageError("strategy_decision.json is required")

    constraints = unique(
        as_list(goal.get("explicit_constraints"))
        + as_list(goal.get("inferred_constraints"))
        + as_list(goal.get("forbidden_actions"))
    ) or ["No explicit constraints were supplied; ask before broadening scope."]

    alternatives = build_alternatives(run_dir, candidates_doc, decision, selected)
    rejected_or_deferred_count = sum(
        1 for item in alternatives if item.get("status") in {"rejected", "deferred", "blocked", "need_user"}
    )

    verifier_requirements = unique(
        as_list(selected.get("verifier_requirements") if isinstance(selected, dict) else [])
        + ["Verifier artifacts and certifier policy are required before final status."]
    )

    search_methods = [
        "candidate_generation",
        "applicability_gate",
        "deterministic_scoring",
        "rejected_or_deferred_branch_recording",
        "tot_style_frontier_bookkeeping",
        "got_style_operation_trace",
        "lats_style_deferred_rollout_record",
    ]
    planning_methods = [
        "deterministic_strategy_selection",
        "milestone_decomposition",
        "local_step_decomposition",
        "artifact_linked_plan_graph",
        "verifier_guided_handoff",
        "failed_branch_reflection_notes",
    ]
    if search_tree:
        planning_methods.append("bounded_planning_tree_search")
        search_methods.append("depth_limited_tree_expansion")
    if adaptive_research:
        planning_methods.append("adaptive_research_risk_review")
        search_methods.append("adaptive_autoresearch_input_recording")

    for planning_input in adaptive_research.get("planning_inputs", []) if isinstance(adaptive_research, dict) else []:
        if isinstance(planning_input, dict):
            verifier_requirements.extend(as_list(planning_input.get("required_verifier_followup")))
    verifier_requirements = unique(verifier_requirements)

    coverage = {
        "schema_version": "planning_coverage_v1",
        "run_id": run_dir.name,
        "generated_by": "planning-coverage-v1",
        "generated_at": utc_now(),
        "authority": {
            "authority_level": "planning_coverage_only",
            "final_status_authority": "certifier_only",
            "can_certify_done": False,
            "claim_exhaustive_planning": False,
            "claim_correctness": False,
        },
        "proof_boundary": {
            "proof_scope": "planning_coverage_only",
            "proves_all_possible_plans": False,
            "proves_artifact_correctness": False,
            "requires_worker_execution": True,
            "requires_verifier_artifacts": True,
            "requires_policy_engine": True,
            "requires_certifier": True,
        },
        "research_basis": RESEARCH_BASIS,
        "source_artifacts": source_artifacts(run_dir),
        "search_budget": {
            "strategy_candidates_count": len(candidates_doc.get("candidates", [])),
            "rejected_or_deferred_count": rejected_or_deferred_count,
            "planning_methods_considered": planning_methods,
            "search_methods_considered": search_methods,
            "search_completeness_claim": "bounded_not_exhaustive",
            "stop_condition": f"{status_note}; execution must stop at verifier/certifier gates before any final-status claim.",
        },
        "goal_coverage": {
            "final_outputs": as_list(goal.get("final_outputs")) or ["artifacts/output.txt"],
            "constraints": constraints,
            "done_criteria": as_list(goal.get("done_criteria")) or ["Verifier must define done criteria before certification."],
            "failure_criteria": as_list(goal.get("failure_criteria")) or ["Missing verifier evidence blocks final status."],
            "ambiguities": as_list(goal.get("ambiguities")),
        },
        "alternatives_considered": alternatives,
        "assumptions": build_assumptions(goal, selected),
        "risk_register": build_risk_register(goal, selected, candidates_doc, adaptive_research),
        "verification_strategy": {
            "verifier_requirements": verifier_requirements,
            "expected_artifacts": expected_artifact_paths(expected_doc, selected, goal),
            "policy_boundary": "Planning coverage can guide verification, but policy_engine.py/certify_run.py own final status.",
            "certifier_handoff": "After worker execution, provide verifier_contract.json and verifier_artifacts/*.json, then run full_verify.py or certify_run.py.",
        },
        "false_done_traps": build_false_done_traps(goal),
        "ask_user_triggers": build_ask_user_triggers(goal, decision),
        "coverage_checks": [],
    }
    coverage["coverage_checks"] = build_coverage_checks(coverage)
    return coverage


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write planning_coverage.json for a run without certifying DONE.")
    parser.add_argument("run", help="Run id or .agentic-runs/<run_id> path")
    args = parser.parse_args(argv)
    try:
        run_dir = resolve_run_dir(args.run)
        coverage = build_planning_coverage(run_dir)
        write_json(run_dir / "planning_coverage.json", coverage)
    except Exception as exc:
        print(f"PLANNING_COVERAGE_FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(coverage, indent=2, ensure_ascii=False))
    return 0 if all(check.get("status") != "FAIL" for check in coverage.get("coverage_checks", [])) else 1


if __name__ == "__main__":
    sys.exit(main())
