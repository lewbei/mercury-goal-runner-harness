#!/usr/bin/env python3
"""Validate planning_search_tree.json.

This validator checks a bounded planning-search trace. It is not a certifier and
must reject exhaustive-search or final-status authority claims.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / ".agentic-pi" / "schemas" / "planning_search_tree.schema.json"
VALIDATE_SCHEMA_PATH = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
FORBIDDEN_STATUS_VALUES = {"DONE_PASS", "DONE_FAIL", "NOT_DONE", "PROVISIONAL_DONE", "CERTIFIED_DONE"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_schema_validator():
    spec = importlib.util.spec_from_file_location("validate_schema_for_planning_search_tree", VALIDATE_SCHEMA_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def path_to_run_dir(path: Path) -> Path:
    if path.is_dir():
        return path
    return path.parent


def recursively_find_forbidden_status_values(value: Any, loc: str = "$", errors: list[str] | None = None) -> list[str]:
    if errors is None:
        errors = []
    if isinstance(value, dict):
        for key, child in value.items():
            recursively_find_forbidden_status_values(child, f"{loc}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            recursively_find_forbidden_status_values(child, f"{loc}[{index}]", errors)
    elif isinstance(value, str) and value in FORBIDDEN_STATUS_VALUES:
        errors.append(f"{loc}: planning search tree must not contain final status value {value!r}")
    return errors


def validate_evidence_refs(refs: list[str], errors: list[str], loc: str) -> None:
    for ref in refs:
        if ref.startswith("/") or ":" in ref.replace("verifier_artifacts/*.json", ""):
            errors.append(f"{loc}: evidence ref must be run-relative/provenance-only, got {ref!r}")
        if ".." in Path(ref).parts:
            errors.append(f"{loc}: evidence ref must not escape run folder, got {ref!r}")


def validate_planning_search_tree(data: dict, *, run_dir: Path | None = None) -> list[str]:
    errors: list[str] = []
    validator = load_schema_validator()
    schema_errors = validator.validate(data, load_json(SCHEMA_PATH))
    errors.extend(f"schema: {item}" for item in schema_errors)
    if schema_errors:
        return errors

    authority = data["authority"]
    if authority.get("can_certify_done") is not False:
        errors.append("authority.can_certify_done must be false")
    if authority.get("claim_exhaustive_search") is not False:
        errors.append("authority.claim_exhaustive_search must be false")
    if authority.get("claim_correctness") is not False:
        errors.append("authority.claim_correctness must be false")
    if authority.get("final_status_authority") != "certifier_only":
        errors.append("final_status_authority must be certifier_only")

    proof_boundary = data["proof_boundary"]
    if proof_boundary.get("proof_scope") != "bounded_planning_trace_only":
        errors.append("proof_boundary.proof_scope must be bounded_planning_trace_only")
    if proof_boundary.get("proves_all_possible_plans") is not False:
        errors.append("proof_boundary.proves_all_possible_plans must be false")
    if proof_boundary.get("proves_artifact_correctness") is not False:
        errors.append("proof_boundary.proves_artifact_correctness must be false")
    for required_gate in ["requires_worker_execution", "requires_verifier_artifacts", "requires_policy_engine", "requires_certifier"]:
        if proof_boundary.get(required_gate) is not True:
            errors.append(f"proof_boundary.{required_gate} must be true")

    boundary = data["implementation_boundary"]
    if boundary.get("source_code_origin") != "harness_native_no_vendor_copy":
        errors.append("implementation_boundary.source_code_origin must be harness_native_no_vendor_copy")
    if boundary.get("external_references_are_design_inputs_only") is not True:
        errors.append("external references must remain design inputs only")
    if boundary.get("planner_can_certify_done") is not False:
        errors.append("implementation_boundary.planner_can_certify_done must be false")

    influence_ids = {item.get("method_id") for item in data.get("method_influences", [])}
    for required in {"tree_of_thoughts_bfs", "graph_of_thoughts_operations", "lats_mcts"}:
        if required not in influence_ids:
            errors.append(f"method_influences missing required inspected method: {required}")
    for item in data.get("method_influences", []):
        if not item.get("inspected_files"):
            errors.append(f"method_influence {item.get('method_id')} must record inspected files")
        not_adapted = str(item.get("not_adapted", "")).lower()
        if (
            "no external code" not in not_adapted
            and "not copied" not in not_adapted
            and "no stochastic" not in not_adapted
            and "vendored" not in not_adapted
        ):
            errors.append(f"method_influence {item.get('method_id')} must state what was not copied/adapted")

    search_config = data["search_config"]
    if search_config.get("completeness_claim") != "bounded_not_exhaustive":
        errors.append("search_config.completeness_claim must be bounded_not_exhaustive")
    if search_config.get("correctness_claim") != "not_proven_by_planning":
        errors.append("search_config.correctness_claim must be not_proven_by_planning")
    if search_config.get("max_depth", 0) < 4:
        errors.append("search_config.max_depth should be at least 4 for deep bounded planning search")
    if search_config.get("beam_width", 0) < 1:
        errors.append("search_config.beam_width must be at least 1")
    if search_config.get("max_iterations", 0) < 1:
        errors.append("search_config.max_iterations must be at least 1")
    if search_config.get("max_rollouts") != 0:
        errors.append("search_config.max_rollouts must be 0 until verifier-backed rollout rewards exist")
    if search_config.get("max_improvement_iterations") != 0:
        errors.append("search_config.max_improvement_iterations must be 0 until graph improvement loops are validated")
    if search_config.get("mcts_optimality_claim") is not False:
        errors.append("search_config.mcts_optimality_claim must be false")
    if "certification" in str(search_config.get("evaluation_policy", "")).lower() and "do not" not in str(search_config.get("evaluation_policy", "")).lower():
        errors.append("evaluation_policy must not treat planning evaluation as certification")

    nodes = data["nodes"]
    edges = data["edges"]
    node_by_id = {}
    for node in nodes:
        node_id = node["node_id"]
        if node_id in node_by_id:
            errors.append(f"duplicate node_id: {node_id}")
        node_by_id[node_id] = node
        validate_evidence_refs(node.get("evidence_refs", []), errors, f"node {node_id} evidence_refs")
        validate_evidence_refs(node.get("planned_evidence_refs", []), errors, f"node {node_id} planned_evidence_refs")
        components = node.get("score_components", {})
        if abs(float(components.get("total", 0)) - float(node.get("score", 0))) > 0.000001:
            errors.append(f"node {node_id} score_components.total must match score")

    root_id = data["root_node_id"]
    if root_id not in node_by_id:
        errors.append("root_node_id is not present in nodes")
    elif node_by_id[root_id].get("parent_id") is not None or node_by_id[root_id].get("depth") != 0:
        errors.append("root node must have parent_id null and depth 0")

    edge_pairs = set()
    child_map = {node_id: [] for node_id in node_by_id}
    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        if source not in node_by_id:
            errors.append(f"edge source missing from nodes: {source}")
            continue
        if target not in node_by_id:
            errors.append(f"edge target missing from nodes: {target}")
            continue
        edge_pairs.add((source, target))
        child_map.setdefault(source, []).append(target)
        target_node = node_by_id[target]
        if target_node.get("parent_id") != source:
            errors.append(f"node {target} parent_id does not match incoming edge source")
        source_depth = node_by_id[source].get("depth", -1)
        target_depth = target_node.get("depth", -1)
        if target_depth != source_depth + 1:
            errors.append(f"edge {source}->{target} must increase depth by exactly 1")

    for node_id, children in child_map.items():
        declared = node_by_id[node_id].get("children", [])
        if sorted(declared) != sorted(children):
            errors.append(f"node {node_id} children do not match outgoing edges")

    selected_path = data["selected_path"]
    if not selected_path or selected_path[0] != root_id:
        errors.append("selected_path must start at root_node_id")
    for node_id in selected_path:
        if node_id not in node_by_id:
            errors.append(f"selected_path node missing from nodes: {node_id}")
    for source, target in zip(selected_path, selected_path[1:]):
        if (source, target) not in edge_pairs:
            errors.append(f"selected_path edge missing: {source}->{target}")
    if len(selected_path) != data["coverage_metrics"].get("selected_path_length"):
        errors.append("coverage_metrics.selected_path_length must match selected_path length")
    for node_id in selected_path:
        status = node_by_id.get(node_id, {}).get("status")
        if status in {"rejected", "blocked", "deferred"}:
            errors.append(f"selected_path must not pass through {status} node: {node_id}")
    selected_strategy_nodes = [
        node_id for node_id in selected_path
        if node_by_id.get(node_id, {}).get("node_type") == "strategy"
        and node_by_id.get(node_id, {}).get("status") == "selected"
    ]

    statuses = {node.get("status") for node in nodes}
    if "selected" not in statuses and "need_user" not in statuses:
        errors.append("tree must contain a selected path or an explicit need_user stop branch")
    if "selected" in statuses and len(selected_strategy_nodes) != 1:
        errors.append("selected runs must route selected_path through exactly one selected strategy node")
    if not any(node.get("status") in {"rejected", "deferred", "blocked", "need_user"} for node in nodes):
        errors.append("tree must record at least one rejected/deferred/blocked/need_user branch")

    max_depth = max(node.get("depth", 0) for node in nodes)
    if max_depth != data["coverage_metrics"].get("max_depth_reached"):
        errors.append("coverage_metrics.max_depth_reached must match nodes")
    if max_depth > search_config.get("max_depth", 0):
        errors.append("coverage_metrics.max_depth_reached must not exceed search_config.max_depth")
    if len(nodes) != data["coverage_metrics"].get("nodes_expanded"):
        errors.append("coverage_metrics.nodes_expanded must match nodes length")
    if len(nodes) > search_config.get("max_nodes", 0):
        errors.append("coverage_metrics.nodes_expanded must not exceed search_config.max_nodes")
    if data["coverage_metrics"].get("candidate_strategy_count", 0) > search_config.get("max_candidate_branches", 0):
        errors.append("candidate_strategy_count must not exceed search_config.max_candidate_branches")
    if data["coverage_metrics"].get("selected_strategy_branch_count", 0) > search_config.get("max_selected_branches", 0):
        errors.append("selected_strategy_branch_count must not exceed search_config.max_selected_branches")
    if len(edges) != data["coverage_metrics"].get("edges_expanded"):
        errors.append("coverage_metrics.edges_expanded must match edges length")
    if len(data["pruned_or_deferred"]) != data["coverage_metrics"].get("pruned_or_deferred_count"):
        errors.append("coverage_metrics.pruned_or_deferred_count must match pruned_or_deferred length")

    pruned_ids = {item["node_id"] for item in data["pruned_or_deferred"]}
    for item in data["pruned_or_deferred"]:
        node = node_by_id.get(item["node_id"])
        if not node:
            errors.append(f"pruned_or_deferred node missing from nodes: {item['node_id']}")
        elif node.get("status") != item.get("status"):
            errors.append(f"pruned_or_deferred status mismatch for {item['node_id']}")
    for node in nodes:
        if node.get("status") in {"rejected", "deferred", "blocked", "need_user"} and node["node_id"] not in pruned_ids:
            errors.append(f"node {node['node_id']} has non-selected status but is missing from pruned_or_deferred")

    candidate_evaluations = data["candidate_evaluations"]
    if len(candidate_evaluations) != data["coverage_metrics"].get("candidate_evaluation_count"):
        errors.append("coverage_metrics.candidate_evaluation_count must match candidate_evaluations length")
    if len(candidate_evaluations) != data["coverage_metrics"].get("candidate_strategy_count"):
        errors.append("candidate_evaluations length must match candidate_strategy_count")
    ranks = [item.get("selection_rank") for item in candidate_evaluations]
    if len(ranks) != len(set(ranks)):
        errors.append("candidate_evaluations selection_rank values must be unique")
    for item in candidate_evaluations:
        node_id = item.get("node_id")
        if node_id not in node_by_id:
            errors.append(f"candidate_evaluation references missing node: {node_id}")
        elif node_by_id[node_id].get("node_type") != "strategy":
            errors.append(f"candidate_evaluation node is not a strategy node: {node_id}")
        if item.get("selection_result") != node_by_id.get(node_id, {}).get("status"):
            errors.append(f"candidate_evaluation selection_result mismatch for {node_id}")

    operation_graph = data["operation_graph"]
    if operation_graph.get("controller_authority") != "planning_only":
        errors.append("operation_graph.controller_authority must be planning_only")
    if operation_graph.get("can_certify_done") is not False:
        errors.append("operation_graph.can_certify_done must be false")
    operation_by_id = {}
    for operation in operation_graph.get("operations", []):
        op_id = operation.get("operation_id")
        if op_id in operation_by_id:
            errors.append(f"duplicate operation_id: {op_id}")
        operation_by_id[op_id] = operation
        if operation.get("operation_type") == "certify":
            errors.append("operation_graph must not contain certify operations")
        if operation.get("authority_level") != "planning_only":
            errors.append(f"operation {op_id} authority_level must be planning_only")
        for field in ["input_node_ids", "output_node_ids"]:
            for node_id in operation.get(field, []):
                if node_id not in node_by_id:
                    errors.append(f"operation {op_id} {field} references missing node: {node_id}")
    for edge in operation_graph.get("operation_edges", []):
        if edge.get("source") not in operation_by_id:
            errors.append(f"operation edge source missing: {edge.get('source')}")
        if edge.get("target") not in operation_by_id:
            errors.append(f"operation edge target missing: {edge.get('target')}")

    search_iterations = data["search_iterations"]
    if len(search_iterations) != data["coverage_metrics"].get("iterations_recorded"):
        errors.append("coverage_metrics.iterations_recorded must match search_iterations length")
    if len(search_iterations) > search_config.get("max_iterations", 0):
        errors.append("search_iterations length must not exceed search_config.max_iterations")
    phases = {item.get("phase") for item in search_iterations}
    for required_phase in {"expand_task_type", "score_strategy_frontier", "record_deferred_expansion"}:
        if required_phase not in phases:
            errors.append(f"search_iterations missing required phase: {required_phase}")
    for item in search_iterations:
        iteration_id = item.get("iteration_id")
        for field in [
            "input_node_ids",
            "generated_node_ids",
            "evaluated_node_ids",
            "selected_node_ids",
            "pruned_or_deferred_node_ids",
            "frontier_after",
        ]:
            for node_id in item.get(field, []):
                if node_id not in node_by_id:
                    errors.append(f"search iteration {iteration_id} {field} references missing node: {node_id}")
        for node_id in item.get("pruned_or_deferred_node_ids", []):
            if node_id not in pruned_ids:
                errors.append(f"search iteration {iteration_id} pruned/deferred node not listed in pruned_or_deferred: {node_id}")

    deferred_methods = data["deferred_expansion_methods"]
    if len(deferred_methods) != data["coverage_metrics"].get("deferred_expansion_method_count"):
        errors.append("coverage_metrics.deferred_expansion_method_count must match deferred_expansion_methods length")
    deferred_ids = {item.get("method_id") for item in deferred_methods}
    for required_method in {"llm_candidate_sampling_and_vote", "graph_aggregate_improve_loop", "mcts_rollout_backpropagation"}:
        if required_method not in deferred_ids:
            errors.append(f"deferred_expansion_methods missing required method: {required_method}")
    for item in deferred_methods:
        boundary_text = str(item.get("authority_boundary", "")).lower()
        if "cannot certify" not in boundary_text:
            errors.append(f"deferred method {item.get('method_id')} must state it cannot certify")
        if not item.get("required_before_enablement"):
            errors.append(f"deferred method {item.get('method_id')} must list enablement requirements")

    errors.extend(recursively_find_forbidden_status_values(data))

    if run_dir is not None:
        if data.get("run_id") != run_dir.name:
            errors.append("run_id must match run directory name")
        for required in ["goal_contract.json", "strategy_candidates.json", "strategy_decision.json"]:
            if not (run_dir / required).is_file():
                errors.append(f"required source artifact missing: {required}")
        for node in nodes:
            for ref in node.get("evidence_refs", []):
                if "*" not in ref and not (run_dir / ref).is_file():
                    errors.append(f"node {node['node_id']} evidence_ref does not exist: {ref}")
        decision_path = run_dir / "strategy_decision.json"
        selected_path_file = run_dir / "selected_strategy.json"
        if decision_path.is_file():
            decision = load_json(decision_path)
            decision_status = decision.get("decision_status")
            expected_selected = decision.get("selected_strategy", "")
            if decision_status == "SELECTED":
                expected_node = f"N.STRATEGY.{expected_selected}"
                if expected_node not in selected_path:
                    # Slug fallback: derive from selected_strategy.json when dots etc. are normalized.
                    if selected_path_file.is_file():
                        selected_doc = load_json(selected_path_file)
                        if selected_doc.get("strategy_id") != expected_selected:
                            errors.append("selected_strategy.json does not match strategy_decision.json")
                    if not any(node_id.startswith("N.STRATEGY.") and node_id.endswith(expected_selected.replace(" ", "_")) for node_id in selected_path):
                        errors.append("selected_path does not include selected strategy from strategy_decision.json")
            elif not any(node_by_id.get(node_id, {}).get("status") == "need_user" for node_id in selected_path):
                errors.append("non-selected strategy decision must route selected_path through need_user")

    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate planning_search_tree.json")
    parser.add_argument("path", help="planning_search_tree.json path or run directory")
    args = parser.parse_args(argv)
    path = Path(args.path)
    tree_path = path / "planning_search_tree.json" if path.is_dir() else path
    if not tree_path.is_file():
        print(f"PLANNING_SEARCH_TREE_INVALID: file missing: {tree_path}")
        return 1
    try:
        data = load_json(tree_path)
        errors = validate_planning_search_tree(data, run_dir=path_to_run_dir(tree_path))
    except Exception as exc:
        print(f"PLANNING_SEARCH_TREE_INVALID: {exc}")
        return 1
    if errors:
        print("PLANNING_SEARCH_TREE_INVALID")
        for item in errors:
            print(f"- {item}")
        return 1
    print("PLANNING_SEARCH_TREE_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
