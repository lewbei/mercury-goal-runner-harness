#!/usr/bin/env python3
"""Deterministic workflow candidate search for v1.9.

This search layer ranks possible harness workflows. It never executes a worker,
never writes status artifacts, and never certifies DONE.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


STATUS_FILES = {"final_status.md", "certification.json", "policy_decision.json"}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def base_nodes(include_domain: bool, include_memory: bool) -> list[dict]:
    nodes = [
        {"node_id": "task_type_router", "role": "route task type"},
    ]
    if include_domain:
        nodes.append({"node_id": "domain_pack_selector", "role": "select advisory domain pack"})
    nodes.extend(
        [
            {"node_id": "strategy_generator", "role": "generate strategy candidates"},
            {"node_id": "strategy_applicability_gate", "role": "reject unsafe strategies"},
        ]
    )
    if include_memory:
        nodes.append({"node_id": "experience_retriever", "role": "retrieve advisory strategy memory"})
    nodes.extend(
        [
            {"node_id": "strategy_scorer", "role": "score candidates"},
            {"node_id": "strategy_selector", "role": "select strategy"},
            {"node_id": "certifier", "role": "final status authority"},
        ]
    )
    return nodes


def edges_for(nodes: list[dict]) -> list[dict]:
    output = []
    for left, right in zip(nodes, nodes[1:]):
        output.append(
            {
                "from": left["node_id"],
                "to": right["node_id"],
                "dependency": "deterministic artifact handoff",
            }
        )
    return output


def trajectory_baseline(run_dir: Path) -> int:
    path = run_dir / "trajectory_score.json"
    if not path.is_file():
        return 80
    score = load_json(path)
    return int(score.get("score", 80))


def drift_risk(run_dir: Path) -> int:
    path = run_dir / "drift_report.json"
    if not path.is_file():
        return 0
    report = load_json(path)
    if report.get("blocking") is True or report.get("drift_level") == "fatal":
        return 5
    if report.get("drift_level") == "repairable":
        return 3
    if report.get("drift_level") == "minor":
        return 1
    return 0


def domain_pack_used(run_dir: Path) -> str:
    path = run_dir / "domain_pack_selection.json"
    if not path.is_file():
        return ""
    selection = load_json(path)
    if selection.get("selection_status") != "SELECTED":
        return ""
    return selection.get("selected_domain_pack", "")


def memory_used(run_dir: Path) -> bool:
    path = run_dir / "retrieved_experience.json"
    if not path.is_file():
        return False
    retrieved = load_json(path)
    return bool(retrieved.get("matched_learning_ids"))


def verifier_strength_path(run_dir: Path) -> str:
    if not (run_dir / "verifier_contract.json").is_file():
        return "none"
    strength_dir = run_dir / "verifier_strength_reports"
    if strength_dir.is_dir():
        for path in sorted(strength_dir.glob("*.json")):
            report = load_json(path)
            if report.get("strength_level") == "certifying":
                return "certifying"
    return "certifying"


def candidate(
    workflow_id: str,
    workflow_name: str,
    run_dir: Path,
    include_domain: bool,
    include_memory: bool,
    false_risk: int,
    cost: int,
    uses_certifier: bool = True,
    writes_status: bool = False,
    writes_verifier: bool = False,
    hides_failed: bool = False,
) -> dict:
    nodes = base_nodes(include_domain, include_memory)
    if not uses_certifier:
        nodes = [node for node in nodes if node["node_id"] != "certifier"]
    return {
        "workflow_id": workflow_id,
        "workflow_name": workflow_name,
        "nodes": nodes,
        "edges": edges_for(nodes),
        "uses_certifier": uses_certifier,
        "writes_status_artifacts": writes_status,
        "writes_verifier_artifacts": writes_verifier,
        "hides_failed_checks": hides_failed,
        "trajectory_score": min(100, trajectory_baseline(run_dir) + (5 if include_domain else 0)),
        "false_certified_done_risk": false_risk,
        "cost_estimate": cost,
        "verifier_strength_path": verifier_strength_path(run_dir),
        "drift_history_risk": drift_risk(run_dir),
        "domain_pack_used": domain_pack_used(run_dir) if include_domain else "",
        "experience_memory_used": memory_used(run_dir) if include_memory else False,
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
    }


def generate_candidates(run_dir: Path) -> list[dict]:
    has_domain = bool(domain_pack_used(run_dir))
    has_memory = memory_used(run_dir)
    return [
        candidate("W.FIXED_POLICY_PIPELINE", "Fixed policy-engine pipeline", run_dir, False, False, 1, 5),
        candidate("W.DOMAIN_MEMORY_POLICY", "Domain and memory informed policy pipeline", run_dir, has_domain, has_memory, 0, 6),
        candidate("W.HIGH_FALSE_CERTIFIED_RISK", "High false-certification risk workflow", run_dir, has_domain, has_memory, 8, 3),
        candidate(
            "W.UNSAFE_BYPASS_CERTIFIER",
            "Unsafe workflow that bypasses certifier",
            run_dir,
            has_domain,
            has_memory,
            10,
            1,
            uses_certifier=False,
            writes_status=True,
        ),
    ]


def rejection_reasons(workflow: dict) -> list[str]:
    reasons = []
    if workflow.get("uses_certifier") is not True:
        reasons.append("workflow bypasses certifier")
    if workflow.get("writes_status_artifacts") is True:
        reasons.append("workflow writes status artifacts outside certifier")
    if workflow.get("writes_verifier_artifacts") is True:
        reasons.append("workflow writes verifier artifacts without authorized path")
    if workflow.get("hides_failed_checks") is True:
        reasons.append("workflow hides failed checks")
    if int(workflow.get("false_certified_done_risk", 0)) >= 5:
        reasons.append("false CERTIFIED_DONE risk too high")
    return reasons


def strength_points(path: str) -> int:
    return {
        "certifying": 20,
        "gating": 10,
        "advisory": 3,
        "none": -10,
    }.get(path, -10)


def score_workflow(workflow: dict) -> dict:
    reasons = rejection_reasons(workflow)
    positives = []
    penalties = []
    if reasons:
        return {
            "workflow_id": workflow["workflow_id"],
            "score": -99,
            "score_level": "rejected",
            "positive_factors": [],
            "penalties": reasons,
        }

    score = workflow["trajectory_score"]
    positives.append("trajectory_score")
    score += strength_points(workflow["verifier_strength_path"])
    positives.append(f"verifier_strength_path:{workflow['verifier_strength_path']}")
    if workflow.get("domain_pack_used"):
        score += 5
        positives.append("domain_pack_used")
    if workflow.get("experience_memory_used"):
        score += 3
        positives.append("experience_memory_used")

    risk_penalty = workflow["false_certified_done_risk"] * 10
    if risk_penalty:
        penalties.append("false_certified_done_risk")
    score -= risk_penalty
    if workflow["cost_estimate"]:
        penalties.append("cost_estimate")
    score -= workflow["cost_estimate"]
    drift_penalty = workflow["drift_history_risk"] * 5
    if drift_penalty:
        penalties.append("drift_history_risk")
    score -= drift_penalty

    if score >= 90:
        level = "preferred"
    elif score >= 60:
        level = "usable"
    else:
        level = "weak"
    return {
        "workflow_id": workflow["workflow_id"],
        "score": score,
        "score_level": level,
        "positive_factors": positives,
        "penalties": penalties,
    }


def status_artifacts_absent(run_dir: Path) -> bool:
    return not any((run_dir / name).exists() for name in STATUS_FILES)


def search_workflows(run_dir: Path) -> dict:
    if not (run_dir / "goal_contract.json").is_file():
        raise FileNotFoundError(f"goal_contract.json missing: {run_dir / 'goal_contract.json'}")
    goal = load_json(run_dir / "goal_contract.json")
    candidates = generate_candidates(run_dir)
    write_json(run_dir / "workflow_candidates.json", {"run_id": goal["run_id"], "candidates": candidates})
    scores = [score_workflow(workflow) for workflow in candidates]
    rejected = [
        {"workflow_id": score["workflow_id"], "reason": "; ".join(score["penalties"])}
        for score in scores
        if score["score_level"] == "rejected"
    ]
    usable = [score for score in scores if score["score_level"] != "rejected"]

    if not usable:
        trace = {
            "run_id": goal["run_id"],
            "generated_by": "workflow-search-v1.9",
            "decision_status": "NO_SAFE_WORKFLOW",
            "selected_workflow": "",
            "reason": "No workflow survived safety rejection.",
            "workflow_scores": scores,
            "rejected_workflows": rejected,
            "selector_checks": ["workflow search did not write certification status artifacts"],
            "final_status_authority": "certifier_only",
            "can_certify_done": False,
        }
        write_json(run_dir / "workflow_search_trace.json", trace)
        return trace

    selected_score = sorted(usable, key=lambda item: (-item["score"], item["workflow_id"]))[0]
    selected = next(workflow for workflow in candidates if workflow["workflow_id"] == selected_score["workflow_id"])
    for score in usable:
        if score["workflow_id"] != selected_score["workflow_id"]:
            rejected.append(
                {
                    "workflow_id": score["workflow_id"],
                    "reason": "not selected by deterministic workflow score ordering",
                }
            )

    trace = {
        "run_id": goal["run_id"],
        "generated_by": "workflow-search-v1.9",
        "decision_status": "SELECTED",
        "selected_workflow": selected["workflow_id"],
        "reason": "Selected workflow has the best deterministic risk-adjusted score and keeps certifier authority.",
        "workflow_scores": scores,
        "rejected_workflows": rejected,
        "selector_checks": [
            "workflow search did not write certification status artifacts",
            f"status artifacts absent before search: {status_artifacts_absent(run_dir)}",
            "selected workflow uses certifier",
        ],
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
    }
    write_json(run_dir / "selected_workflow.json", selected)
    write_json(run_dir / "workflow_search_trace.json", trace)
    return trace


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Search deterministic workflow candidates without certifying DONE.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    try:
        trace = search_workflows(Path(args.run_dir))
    except Exception as exc:
        print(f"WORKFLOW_SEARCH_FAILED: {exc}")
        return 1
    print(json.dumps(trace, indent=2, ensure_ascii=False))
    return 0 if trace["decision_status"] == "SELECTED" else 1


if __name__ == "__main__":
    sys.exit(main())
