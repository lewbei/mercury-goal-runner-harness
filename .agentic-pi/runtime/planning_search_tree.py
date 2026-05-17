#!/usr/bin/env python3
"""Build a deterministic bounded planning search tree for one run.

The tree makes planning branches inspectable: task type, strategy candidates,
execution branch, verifier branch, risk branch, and deferred/blocked branches.
It is a bounded search trace, not proof of exhaustive search and not final
status authority.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = ROOT / ".agentic-runs"
STATUS_ARTIFACTS = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}
MAX_DEPTH = 5
MAX_ITERATIONS = 4
MAX_NODES = 64
MAX_CANDIDATE_BRANCHES = 12
MAX_SELECTED_BRANCHES = 1
MAX_ROLLOUTS = 0
MAX_IMPROVEMENT_ITERATIONS = 0
BEAM_WIDTH = 3

METHOD_INFLUENCES = [
    {
        "method_id": "tree_of_thoughts_bfs",
        "source": "princeton-nlp/tree-of-thought-llm",
        "inspected_files": ["src/tot/methods/bfs.py", "run.py"],
        "adapted_lesson": "Make generation, evaluation, and selection phases explicit, with a bounded frontier instead of one opaque plan.",
        "not_adapted": "No external code, LLM sampling loop, or self-reported vote authority is copied into the harness.",
    },
    {
        "method_id": "graph_of_thoughts_operations",
        "source": "spcl/graph-of-thoughts",
        "inspected_files": ["graph_of_thoughts/operations/operations.py", "graph_of_thoughts/controller/controller.py"],
        "adapted_lesson": "Represent planning as inspectable operations over nodes and edges, while keeping controller authority separate from certification.",
        "not_adapted": "No graph executor, optimizer, or aggregation code is vendored; graph-style expansion remains a bounded trace.",
    },
    {
        "method_id": "lats_mcts",
        "source": "lapisrocks/LanguageAgentTreeSearch",
        "inspected_files": ["programming/mcts.py", "hotpot/lats.py", "webshop/lats.py"],
        "adapted_lesson": "Record selection, expansion, evaluation, deferred rollout/backpropagation, failed-branch lessons, and terminal risk boundaries.",
        "not_adapted": "No stochastic UCT rollout, environment interaction, reward claim, or success certification is executed by this planner.",
    },
    {
        "method_id": "adaptive_autoresearch_provenance",
        "source": "saved run-local adaptive_research_inputs.json plus reproducibility/eval guidance",
        "inspected_files": [".agentic-pi/runtime/adaptive_research_inputs.py", ".agentic-pi/validators/validate_adaptive_research_inputs.py"],
        "adapted_lesson": "Allow nondeterministic research to widen planning questions only after it is saved as provenance and validated deterministically.",
        "not_adapted": "No external code, live network fetch, mutable research claim, or final-status authority is copied into this planning tree.",
    },
]

DEFERRED_EXPANSION_METHODS = [
    {
        "method_id": "llm_candidate_sampling_and_vote",
        "source_method": "Tree-of-Thoughts sample/propose plus value/vote selection",
        "reason_deferred": "This strict harness path uses deterministic strategy candidates; live LLM branch generation would need separate prompt provenance and verifier fixtures.",
        "required_before_enablement": [
            "run-local prompt provenance for every sampled branch",
            "deterministic replay fixture for sampled candidates",
            "validator proving sampled branches cannot write authority artifacts",
        ],
        "authority_boundary": "planning-only; cannot certify DONE",
    },
    {
        "method_id": "graph_aggregate_improve_loop",
        "source_method": "Graph-of-Thoughts generate/score/validate/improve/aggregate operations",
        "reason_deferred": "The current artifact records graph-shaped edges but does not run multi-operation improvement loops or aggregate plans as proof.",
        "required_before_enablement": [
            "operation schema with explicit inputs and outputs",
            "cycle/dependency validator",
            "independent verifier handoff for aggregated branches",
        ],
        "authority_boundary": "planning-only; cannot certify DONE",
    },
    {
        "method_id": "mcts_rollout_backpropagation",
        "source_method": "LATS/MCTS select, expand, evaluate, rollout, and backpropagate",
        "reason_deferred": "Rollouts require executable environments and reward models; this planner only records deterministic proxy scores and risk notes.",
        "required_before_enablement": [
            "bounded rollout budget in run config",
            "reward provenance tied to verifier artifacts",
            "policy gate preventing reward from becoming final status",
        ],
        "authority_boundary": "planning-only; cannot certify DONE",
    },
    {
        "method_id": "live_adaptive_autoresearch_sampling",
        "source_method": "Non-deterministic LLM/web research used to propose planning inputs",
        "reason_deferred": "Live research can be useful, but deterministic validators may only consume saved run-local provenance artifacts.",
        "required_before_enablement": [
            "adaptive_research_inputs.json with source URLs, queries/prompts, hashes, and model/request metadata",
            "validator proving research inputs cannot write authority artifacts or certify DONE",
            "verifier follow-up for any research-backed plan change",
        ],
        "authority_boundary": "planning-only; cannot certify DONE",
    },
]


class PlanningSearchTreeError(RuntimeError):
    """Raised when a planning search tree cannot be built safely."""


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
        raise PlanningSearchTreeError(f"run directory must be under .agentic-runs: {raw}")
    if not run_dir.is_dir():
        raise PlanningSearchTreeError(f"run directory missing: {raw}")
    return run_dir


def slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return text.strip("_") or "unknown"


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def unique(items: list[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output


def build_score_components(
    total: float,
    *,
    base_strategy_score: float = 0.0,
    applicability_adjustment: float = 0.0,
    verifier_path_bonus: float = 0.0,
    risk_penalty: float = 0.0,
    selection_adjustment: float = 0.0,
) -> dict[str, float]:
    """Expose how a deterministic proxy score was derived.

    The components are audit breadcrumbs, not statistical proof. The bounded
    budget adjustment is computed last so component totals always reconcile with
    the node score emitted in the tree.
    """
    subtotal = (
        base_strategy_score
        + applicability_adjustment
        + verifier_path_bonus
        + risk_penalty
        + selection_adjustment
    )
    return {
        "base_strategy_score": round(float(base_strategy_score), 6),
        "applicability_adjustment": round(float(applicability_adjustment), 6),
        "verifier_path_bonus": round(float(verifier_path_bonus), 6),
        "risk_penalty": round(float(risk_penalty), 6),
        "selection_adjustment": round(float(selection_adjustment), 6),
        "bounded_budget_adjustment": round(float(total) - subtotal, 6),
        "total": round(float(total), 6),
    }


class TreeBuilder:
    def __init__(self) -> None:
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, str]] = []
        self.children_by_id: dict[str, list[str]] = {}

    def add_node(
        self,
        *,
        node_id: str,
        parent_id: str | None,
        depth: int,
        node_type: str,
        status: str,
        summary: str,
        score: float,
        score_reasons: list[str],
        evidence_refs: list[str],
        relation: str = "expands_to",
        score_components: dict[str, float] | None = None,
        planned_evidence_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        if any(node["node_id"] == node_id for node in self.nodes):
            raise PlanningSearchTreeError(f"duplicate search-tree node id: {node_id}")
        node = {
            "node_id": node_id,
            "parent_id": parent_id,
            "depth": depth,
            "node_type": node_type,
            "status": status,
            "summary": summary,
            "score": score,
            "score_components": score_components or build_score_components(score),
            "score_reasons": score_reasons or ["deterministic planning search bookkeeping"],
            "evidence_refs": evidence_refs,
            "planned_evidence_refs": planned_evidence_refs or [],
            "children": [],
        }
        self.nodes.append(node)
        self.children_by_id[node_id] = node["children"]
        if parent_id is not None:
            self.children_by_id.setdefault(parent_id, []).append(node_id)
            self.edges.append({"source": parent_id, "target": node_id, "relation": relation})
        return node


def score_by_id(scores_doc: dict) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("strategy_id")): item
        for item in scores_doc.get("scores", [])
        if isinstance(item, dict) and item.get("strategy_id")
    }


def applicability_maps(applicability: dict) -> tuple[set[str], dict[str, list[str]]]:
    applicable = {
        str(item.get("strategy_id"))
        for item in applicability.get("applicable_strategies", [])
        if isinstance(item, dict) and item.get("strategy_id")
    }
    blocked = {
        str(item.get("strategy_id")): as_list(item.get("block_reasons"))
        for item in applicability.get("blocked_strategies", [])
        if isinstance(item, dict) and item.get("strategy_id")
    }
    return applicable, blocked


def rejected_reasons(decision: dict) -> dict[str, str]:
    return {
        str(item.get("strategy_id")): str(item.get("reason") or "not selected by deterministic strategy ordering")
        for item in decision.get("rejected_strategies", [])
        if isinstance(item, dict) and item.get("strategy_id")
    }


def choose_selected_path(tree: TreeBuilder, selected_strategy_id: str, decision_status: str) -> list[str]:
    if decision_status != "SELECTED" or not selected_strategy_id:
        stop_nodes = [
            node["node_id"]
            for node in tree.nodes
            if node.get("status") == "need_user" and node.get("node_type") == "stop_branch"
        ]
        if stop_nodes:
            return ["N.ROOT", "N.TASK_TYPE", stop_nodes[0]]
        need_user_nodes = [
            node["node_id"]
            for node in tree.nodes
            if node.get("status") == "need_user" and node["node_id"] != "N.TASK_TYPE"
        ]
        if need_user_nodes:
            return ["N.ROOT", "N.TASK_TYPE", need_user_nodes[0]]
        return ["N.ROOT", "N.TASK_TYPE"]

    path = ["N.ROOT", "N.TASK_TYPE", f"N.STRATEGY.{slug(selected_strategy_id)}"]
    for suffix in ["EXECUTE", "VERIFY", "RISK"]:
        node_id = f"N.{suffix}.{slug(selected_strategy_id)}"
        if any(node["node_id"] == node_id for node in tree.nodes):
            path.append(node_id)
    return path


def selected_strategy_id(decision: dict, selected_doc: dict) -> str:
    return str(decision.get("selected_strategy") or selected_doc.get("strategy_id") or "").strip()


def build_pruned_or_deferred(tree: TreeBuilder) -> list[dict[str, str]]:
    output = []
    for node in tree.nodes:
        status = node.get("status")
        if status in {"rejected", "deferred", "blocked", "need_user"}:
            output.append({
                "node_id": node["node_id"],
                "status": status,
                "reason": "; ".join(node.get("score_reasons", [])),
            })
    if not output:
        output.append({
            "node_id": "N.DEFER.EXPANDED_SEARCH",
            "status": "deferred",
            "reason": "No candidate branch was rejected; expanded tree/graph search remains deferred by bounded search budget.",
        })
    return output


def node_by_id(tree: TreeBuilder) -> dict[str, dict[str, Any]]:
    return {node["node_id"]: node for node in tree.nodes}


def split_evidence_refs(run_dir: Path, refs: list[str]) -> tuple[list[str], list[str]]:
    existing: list[str] = []
    planned: list[str] = []
    for ref in refs:
        if "*" in ref:
            planned.append(ref)
            continue
        if (run_dir / ref).is_file():
            existing.append(ref)
        else:
            planned.append(ref)
    return unique(existing), unique(planned)


def classify_node_evidence_refs(run_dir: Path, tree: TreeBuilder) -> None:
    """Keep present inputs separate from future/planned verifier handoff refs."""
    for node in tree.nodes:
        existing, planned = split_evidence_refs(run_dir, node.get("evidence_refs", []))
        node["evidence_refs"] = existing
        node["planned_evidence_refs"] = unique(node.get("planned_evidence_refs", []) + planned)


def build_candidate_evaluations(
    tree: TreeBuilder,
    *,
    candidates: list[dict[str, Any]],
    scores: dict[str, dict[str, Any]],
    applicable_ids: set[str],
    blocked_by_id: dict[str, list[str]],
    selected_id: str,
) -> list[dict[str, Any]]:
    nodes = node_by_id(tree)
    ranked = sorted(
        candidates,
        key=lambda candidate: float(scores.get(str(candidate.get("strategy_id")), {}).get("score", 0)),
        reverse=True,
    )
    evaluations: list[dict[str, Any]] = []
    for rank, candidate in enumerate(ranked, start=1):
        strategy_id = str(candidate.get("strategy_id") or "S.UNKNOWN").strip()
        node_id = f"N.STRATEGY.{slug(strategy_id)}"
        node = nodes.get(node_id, {})
        score_doc = scores.get(strategy_id, {})
        if strategy_id in blocked_by_id:
            applicability_status = "blocked"
        elif not applicable_ids or strategy_id in applicable_ids:
            applicability_status = "applicable"
        else:
            applicability_status = "not_applicable"
        selection_result = str(node.get("status") or "deferred")
        if strategy_id == selected_id and selection_result == "selected":
            selection_result = "selected"
        evaluations.append(
            {
                "strategy_id": strategy_id,
                "node_id": node_id,
                "applicability_status": applicability_status,
                "score": float(node.get("score", score_doc.get("score", 0))),
                "score_level": str(score_doc.get("score_level") or "unscored"),
                "positive_factors": as_list(score_doc.get("positive_factors")),
                "penalties": as_list(score_doc.get("penalties")) + blocked_by_id.get(strategy_id, []),
                "selection_rank": rank,
                "selection_result": selection_result,
                "decision_reason": "; ".join(node.get("score_reasons", [])) or "No decision reason recorded.",
            }
        )
    return evaluations


def build_operation_graph(tree: TreeBuilder, selected_path: list[str], pruned_or_deferred: list[dict[str, str]]) -> dict[str, Any]:
    nodes = node_by_id(tree)
    task_frontier = list(tree.children_by_id.get("N.TASK_TYPE", []))
    pruned_ids = [item["node_id"] for item in pruned_or_deferred if item.get("node_id") in nodes]
    operations = [
        {
            "operation_id": "OP.GENERATE_TASK_TYPE",
            "operation_type": "generate",
            "authority_level": "planning_only",
            "input_node_ids": ["N.ROOT"],
            "output_node_ids": ["N.TASK_TYPE"] if "N.TASK_TYPE" in nodes else [],
            "description": "Generate task-type node from run-local goal artifacts.",
        },
        {
            "operation_id": "OP.GENERATE_STRATEGY_FRONTIER",
            "operation_type": "generate",
            "authority_level": "planning_only",
            "input_node_ids": ["N.TASK_TYPE"] if "N.TASK_TYPE" in nodes else [],
            "output_node_ids": task_frontier,
            "description": "Generate strategy frontier including selected, rejected, blocked, need-user, and deferred branches.",
        },
        {
            "operation_id": "OP.SCORE_AND_VALIDATE_FRONTIER",
            "operation_type": "score",
            "authority_level": "planning_only",
            "input_node_ids": task_frontier,
            "output_node_ids": task_frontier,
            "description": "Score deterministic candidates and validate applicability without certifying final status.",
        },
        {
            "operation_id": "OP.SELECT_OR_DEFER",
            "operation_type": "select",
            "authority_level": "planning_only",
            "input_node_ids": task_frontier,
            "output_node_ids": selected_path + pruned_ids,
            "description": "Select the safe bounded path or defer/stop branches while keeping pruned branches visible.",
        },
        {
            "operation_id": "OP.HANDOFF_VERIFIER_RISK",
            "operation_type": "handoff",
            "authority_level": "planning_only",
            "input_node_ids": selected_path,
            "output_node_ids": [node_id for node_id in selected_path if node_id in nodes],
            "description": "Expose verifier and risk handoff obligations; worker, policy, and certifier remain separate.",
        },
    ]
    return {
        "graph_kind": "planning_operation_dag",
        "controller": "deterministic_strategy_selector",
        "controller_authority": "planning_only",
        "can_certify_done": False,
        "operations": operations,
        "operation_edges": [
            {"source": "OP.GENERATE_TASK_TYPE", "target": "OP.GENERATE_STRATEGY_FRONTIER", "relation": "feeds"},
            {"source": "OP.GENERATE_STRATEGY_FRONTIER", "target": "OP.SCORE_AND_VALIDATE_FRONTIER", "relation": "feeds"},
            {"source": "OP.SCORE_AND_VALIDATE_FRONTIER", "target": "OP.SELECT_OR_DEFER", "relation": "feeds"},
            {"source": "OP.SELECT_OR_DEFER", "target": "OP.HANDOFF_VERIFIER_RISK", "relation": "feeds"},
        ],
    }


def build_search_iterations(
    tree: TreeBuilder,
    *,
    selected_path: list[str],
    pruned_or_deferred: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Build an inspectable deterministic search trace.

    This borrows the *shape* of tree-search bookkeeping (frontier, evaluate,
    select, defer) without executing stochastic rollouts or claiming reward.
    """
    nodes = node_by_id(tree)
    task_type_id = "N.TASK_TYPE"
    task_frontier = list(tree.children_by_id.get(task_type_id, []))
    selected_frontier = [node_id for node_id in task_frontier if nodes[node_id].get("status") == "selected"]
    if not selected_frontier:
        selected_frontier = [node_id for node_id in task_frontier if nodes[node_id].get("status") == "need_user"]
    pruned_ids = [item["node_id"] for item in pruned_or_deferred if item.get("node_id") in nodes]
    non_selected_frontier = [node_id for node_id in task_frontier if node_id in pruned_ids]
    deep_selected_nodes = [
        node_id for node_id in selected_path
        if node_id in nodes and nodes[node_id].get("depth", 0) >= 3
    ]
    deferred_node_ids = [node_id for node_id in pruned_ids if nodes[node_id].get("status") == "deferred"]

    iterations = [
        {
            "iteration_id": "I.001_ROOT_TO_TASK_TYPE",
            "phase": "expand_task_type",
            "input_node_ids": ["N.ROOT"],
            "generated_node_ids": [task_type_id] if task_type_id in nodes else [],
            "evaluated_node_ids": [task_type_id] if task_type_id in nodes else [],
            "selected_node_ids": [task_type_id] if task_type_id in selected_path else [],
            "pruned_or_deferred_node_ids": [],
            "frontier_after": task_frontier,
            "notes": [
                "Task-type expansion is deterministic and run-local.",
                "This is generation/evaluation bookkeeping, not certification.",
            ],
        },
        {
            "iteration_id": "I.002_SCORE_STRATEGY_FRONTIER",
            "phase": "score_strategy_frontier",
            "input_node_ids": [task_type_id] if task_type_id in nodes else [],
            "generated_node_ids": task_frontier,
            "evaluated_node_ids": task_frontier,
            "selected_node_ids": selected_frontier,
            "pruned_or_deferred_node_ids": non_selected_frontier,
            "frontier_after": selected_frontier,
            "notes": [
                f"Beam width is capped at {BEAM_WIDTH}; deterministic scores and applicability gates select the frontier.",
                "Rejected, blocked, need-user, and deferred branches remain visible instead of being erased.",
            ],
        },
    ]

    if deep_selected_nodes:
        parent_inputs = selected_frontier or [selected_path[-1]]
        iterations.append(
            {
                "iteration_id": "I.003_DEEPEN_SELECTED_BRANCH",
                "phase": "deepen_selected_branch",
                "input_node_ids": parent_inputs,
                "generated_node_ids": deep_selected_nodes,
                "evaluated_node_ids": deep_selected_nodes,
                "selected_node_ids": deep_selected_nodes,
                "pruned_or_deferred_node_ids": [],
                "frontier_after": [],
                "notes": [
                    "Selected execution, verifier, and risk branches are expanded to keep handoff obligations inspectable.",
                    "Worker execution and certifier policy remain outside the planning tree.",
                ],
            }
        )

    iterations.append(
        {
            "iteration_id": f"I.{len(iterations) + 1:03d}_RECORD_DEFERRED_EXPANSION",
            "phase": "record_deferred_expansion",
            "input_node_ids": selected_path,
            "generated_node_ids": [],
            "evaluated_node_ids": deferred_node_ids,
            "selected_node_ids": [],
            "pruned_or_deferred_node_ids": deferred_node_ids,
            "frontier_after": [],
            "notes": [
                "ToT-style LLM voting, GoT-style aggregation, and LATS/MCTS rollouts are recorded as deferred methods.",
                "Deferred methods cannot become final-status authority without independent verifier and certifier gates.",
            ],
        }
    )
    return iterations


def build_planning_search_tree(run_dir: Path) -> dict[str, Any]:
    goal = load_json(run_dir / "goal_contract.json", {}) or {}
    task_type_doc = load_json(run_dir / "task_type_decision.json", {}) or {}
    candidates_doc = load_json(run_dir / "strategy_candidates.json", {}) or {}
    applicability = load_json(run_dir / "strategy_applicability.json", {}) or {}
    scores_doc = load_json(run_dir / "strategy_scores.json", {}) or {}
    decision = load_json(run_dir / "strategy_decision.json", {}) or {}
    selected_doc = load_json(run_dir / "selected_strategy.json", {}) or {}
    adaptive_research = load_json(run_dir / "adaptive_research_inputs.json", {}) or {}

    if not goal:
        raise PlanningSearchTreeError("goal_contract.json is required")
    if not candidates_doc:
        raise PlanningSearchTreeError("strategy_candidates.json is required")
    if not decision:
        raise PlanningSearchTreeError("strategy_decision.json is required")

    task_type = str(task_type_doc.get("task_type") or candidates_doc.get("task_type") or selected_doc.get("task_type") or "unknown")
    selected_id = selected_strategy_id(decision, selected_doc)
    decision_status = str(decision.get("decision_status") or "UNKNOWN")
    applicable_ids, blocked_by_id = applicability_maps(applicability)
    scores = score_by_id(scores_doc)
    rejected = rejected_reasons(decision)

    tree = TreeBuilder()
    status_note = (
        "status artifacts already exist; search remains non-authoritative"
        if any((run_dir / name).exists() for name in STATUS_ARTIFACTS)
        else "status artifacts absent during search-tree build"
    )

    tree.add_node(
        node_id="N.ROOT",
        parent_id=None,
        depth=0,
        node_type="root",
        status="expanded",
        summary="Bounded planning search root for the run goal.",
        score=0,
        score_reasons=["root of deterministic bounded tree search", status_note],
        evidence_refs=["goal_contract.json"],
    )
    tree.add_node(
        node_id="N.TASK_TYPE",
        parent_id="N.ROOT",
        depth=1,
        node_type="task_type",
        status="expanded" if task_type != "unknown" else "need_user",
        summary=f"Task type considered: {task_type}",
        score=1 if task_type != "unknown" else -10,
        score_reasons=["task type came from task_type_decision.json or strategy candidates"],
        evidence_refs=["task_type_decision.json", "strategy_candidates.json"],
    )

    if adaptive_research:
        finding_count = len(adaptive_research.get("findings", []))
        planning_input_count = len(adaptive_research.get("planning_inputs", []))
        tree.add_node(
            node_id="N.STRATEGY.ADAPTIVE_RESEARCH_INPUTS",
            parent_id="N.TASK_TYPE",
            depth=2,
            node_type="strategy",
            status="deferred",
            summary="Adaptive/autoresearch inputs are recorded as planning-only evidence, not execution or certification authority.",
            score=0,
            score_reasons=[
                f"adaptive_research_inputs.json recorded {finding_count} findings and {planning_input_count} planning inputs",
                "nondeterministic research can shape questions and verifier follow-up only after deterministic validation",
                "adaptive research cannot certify DONE",
            ],
            evidence_refs=["adaptive_research_inputs.json"],
            relation="defers",
        )

    candidates = [item for item in candidates_doc.get("candidates", []) if isinstance(item, dict)]
    for candidate in candidates:
        strategy_id = str(candidate.get("strategy_id") or "S.UNKNOWN").strip()
        score_doc = scores.get(strategy_id, {})
        raw_score = float(score_doc.get("score", 0))
        score_value = raw_score
        evidence_refs = ["strategy_candidates.json", "strategy_scores.json", "strategy_applicability.json"]
        if strategy_id == selected_id and decision_status == "SELECTED":
            status = "selected"
            relation = "selects"
            score_reasons = unique(as_list(score_doc.get("positive_factors")) + [str(decision.get("reason") or "selected strategy")])
        elif strategy_id in blocked_by_id:
            status = "blocked"
            relation = "prunes"
            score_value = -99
            score_reasons = blocked_by_id[strategy_id]
        elif strategy_id in rejected:
            status = "rejected"
            relation = "prunes"
            score_reasons = [rejected[strategy_id]]
        elif strategy_id not in applicable_ids and applicable_ids:
            status = "rejected"
            relation = "prunes"
            score_reasons = ["not present in applicable strategy set"]
        else:
            status = "deferred"
            relation = "defers"
            score_reasons = ["candidate remained unselected in bounded search"]

        strategy_node_id = f"N.STRATEGY.{slug(strategy_id)}"
        tree.add_node(
            node_id=strategy_node_id,
            parent_id="N.TASK_TYPE",
            depth=2,
            node_type="strategy",
            status=status,
            summary=f"Strategy branch: {strategy_id}",
            score=score_value,
            score_components=build_score_components(score_value, base_strategy_score=raw_score),
            score_reasons=score_reasons,
            evidence_refs=evidence_refs,
            relation=relation,
        )

        if status == "selected":
            verifier_delta = 2 if candidate.get("can_reach_certifying_evidence") else -2
            exec_score = score_value + verifier_delta
            tree.add_node(
                node_id=f"N.EXECUTE.{slug(strategy_id)}",
                parent_id=strategy_node_id,
                depth=3,
                node_type="execution_branch",
                status="selected",
                summary="Selected execution branch prepares run-local artifacts only.",
                score=exec_score,
                score_components=build_score_components(
                    exec_score,
                    base_strategy_score=score_value,
                    verifier_path_bonus=verifier_delta,
                ),
                score_reasons=[
                    "worker execution is still separate from planning",
                    "write scope must be enforced by expected_artifacts.json",
                ],
                evidence_refs=["selected_strategy.json", "expected_artifacts.json", "merged_plan.json"],
                relation="selects",
            )
            verifier_requirements = as_list(candidate.get("verifier_requirements")) or [
                "verifier evidence must be provided before final status"
            ]
            verifier_score = exec_score + len(verifier_requirements)
            tree.add_node(
                node_id=f"N.VERIFY.{slug(strategy_id)}",
                parent_id=f"N.EXECUTE.{slug(strategy_id)}",
                depth=4,
                node_type="verifier_branch",
                status="selected",
                summary="Verifier branch records checks that must exist before certifier handoff.",
                score=verifier_score,
                score_components=build_score_components(
                    verifier_score,
                    base_strategy_score=score_value,
                    verifier_path_bonus=verifier_delta + len(verifier_requirements),
                ),
                score_reasons=verifier_requirements,
                evidence_refs=["selected_strategy.json", "verifier_contract.json", "verifier_artifacts/*.json"],
                relation="selects",
            )
            risks = unique(as_list(candidate.get("risk_notes")) + ["false-DONE risk remains until certifier policy runs"])
            tree.add_node(
                node_id=f"N.RISK.{slug(strategy_id)}",
                parent_id=f"N.VERIFY.{slug(strategy_id)}",
                depth=5,
                node_type="risk_branch",
                status="terminal",
                summary="Risk branch keeps known failure modes visible after selection.",
                score=exec_score,
                score_components=build_score_components(
                    exec_score,
                    base_strategy_score=score_value,
                    verifier_path_bonus=verifier_delta,
                ),
                score_reasons=risks,
                evidence_refs=["strategy_candidates.json", "planning_coverage.json"],
                relation="selects",
            )

    if decision_status != "SELECTED":
        tree.add_node(
            node_id="N.STOP.NEED_USER_STRATEGY",
            parent_id="N.TASK_TYPE",
            depth=2,
            node_type="stop_branch",
            status="need_user",
            summary="No safe strategy selected; user strategy direction is required before execution.",
            score=-100,
            score_reasons=[str(decision.get("reason") or "strategy_decision.json did not select a strategy")],
            evidence_refs=["strategy_decision.json"],
            relation="defers",
        )

    tree.add_node(
        node_id="N.DEFER.EXPANDED_SEARCH",
        parent_id="N.TASK_TYPE",
        depth=2,
        node_type="strategy",
        status="deferred",
        summary="Higher-cost tree/graph/MCTS expansion is recorded but not executed by this deterministic bounded search.",
        score=0,
        score_reasons=["bounded search records this branch instead of pretending exhaustive planning"],
        evidence_refs=["planning_search_tree.json"],
        relation="defers",
    )

    classify_node_evidence_refs(run_dir, tree)
    selected_path = choose_selected_path(tree, selected_id, decision_status)
    pruned_or_deferred = build_pruned_or_deferred(tree)
    search_iterations = build_search_iterations(
        tree,
        selected_path=selected_path,
        pruned_or_deferred=pruned_or_deferred,
    )
    candidate_evaluations = build_candidate_evaluations(
        tree,
        candidates=candidates,
        scores=scores,
        applicable_ids=applicable_ids,
        blocked_by_id=blocked_by_id,
        selected_id=selected_id,
    )
    operation_graph = build_operation_graph(tree, selected_path, pruned_or_deferred)
    max_depth = max(node["depth"] for node in tree.nodes)
    return {
        "schema_version": "planning_search_tree_v1",
        "run_id": run_dir.name,
        "generated_by": "planning-search-tree-v1",
        "generated_at": utc_now(),
        "authority": {
            "authority_level": "planning_search_only",
            "final_status_authority": "certifier_only",
            "can_certify_done": False,
            "claim_exhaustive_search": False,
            "claim_correctness": False,
        },
        "proof_boundary": {
            "proof_scope": "bounded_planning_trace_only",
            "proves_all_possible_plans": False,
            "proves_artifact_correctness": False,
            "requires_worker_execution": True,
            "requires_verifier_artifacts": True,
            "requires_policy_engine": True,
            "requires_certifier": True,
        },
        "implementation_boundary": {
            "source_code_origin": "harness_native_no_vendor_copy",
            "external_references_are_design_inputs_only": True,
            "planner_can_certify_done": False,
        },
        "method_influences": METHOD_INFLUENCES,
        "search_config": {
            "algorithm": "bounded_best_first_tree_search",
            "max_depth": MAX_DEPTH,
            "max_iterations": MAX_ITERATIONS,
            "max_nodes": MAX_NODES,
            "max_candidate_branches": MAX_CANDIDATE_BRANCHES,
            "max_selected_branches": MAX_SELECTED_BRANCHES,
            "max_rollouts": MAX_ROLLOUTS,
            "max_improvement_iterations": MAX_IMPROVEMENT_ITERATIONS,
            "beam_width": BEAM_WIDTH,
            "mcts_optimality_claim": False,
            "branching_policy": "Expand task type, strategy candidates, selected execution, verifier handoff, and risk branch; defer higher-cost graph/MCTS expansion.",
            "generation_policy": "Generate run-local nodes only from existing goal, task type, strategy, expected artifact, adaptive research provenance, and verifier-handoff artifacts.",
            "evaluation_policy": "Evaluate deterministic proxy scores, applicability gates, saved adaptive research provenance, verifier-path presence, and risk notes; do not treat reward or research as certification.",
            "selection_policy": "Select the highest safe deterministic strategy frontier or route to NEED_USER_STRATEGY; keep rejected/deferred branches inspectable.",
            "scoring_policy": "Expose score_components on every node so strategy score, applicability, verifier path, risk, and bounded-budget effects are auditable.",
            "reflection_policy": "Failed/blocked/deferred branches are recorded as score reasons and pruned_or_deferred entries, not hidden or rewritten.",
            "backpropagation_policy": "MCTS-style rollout and backpropagation are deferred until rewards are verifier-backed and policy-gated.",
            "stop_condition": "Stop after selected verifier/risk branch or NEED_USER_STRATEGY; do not execute worker or certify final status.",
            "completeness_claim": "bounded_not_exhaustive",
            "correctness_claim": "not_proven_by_planning",
        },
        "root_node_id": "N.ROOT",
        "nodes": tree.nodes,
        "edges": tree.edges,
        "selected_path": selected_path,
        "pruned_or_deferred": pruned_or_deferred,
        "search_iterations": search_iterations,
        "candidate_evaluations": candidate_evaluations,
        "operation_graph": operation_graph,
        "deferred_expansion_methods": DEFERRED_EXPANSION_METHODS,
        "coverage_metrics": {
            "nodes_expanded": len(tree.nodes),
            "edges_expanded": len(tree.edges),
            "max_depth_reached": max_depth,
            "selected_path_length": len(selected_path),
            "candidate_strategy_count": len(candidates),
            "candidate_evaluation_count": len(candidate_evaluations),
            "selected_strategy_branch_count": len([node for node in tree.nodes if node.get("node_type") == "strategy" and node.get("status") == "selected"]),
            "pruned_or_deferred_count": len(pruned_or_deferred),
            "iterations_recorded": len(search_iterations),
            "deferred_expansion_method_count": len(DEFERRED_EXPANSION_METHODS),
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write planning_search_tree.json for a run without certifying DONE.")
    parser.add_argument("run", help="Run id or .agentic-runs/<run_id> path")
    args = parser.parse_args(argv)
    try:
        run_dir = resolve_run_dir(args.run)
        tree = build_planning_search_tree(run_dir)
        write_json(run_dir / "planning_search_tree.json", tree)
    except Exception as exc:
        print(f"PLANNING_SEARCH_TREE_FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(tree, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
