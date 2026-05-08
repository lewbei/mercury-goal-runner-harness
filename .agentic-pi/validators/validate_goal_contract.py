import json
from pathlib import Path

ALLOWED_NODE_TYPES = {"raw_goal", "goal_contract", "constraint", "success_criteria"}
ALLOWED_EDGE_TYPES = {"defines", "constrains", "requires_success", "generates_seed"}


def validate_goal_contract(graph_path: str):
    """Validate a Goal Contract graph JSON file.

    Returns a list of error strings; empty list means success.
    """
    path = Path(graph_path)
    if not path.is_file():
        return [f"File not found: {graph_path}"]
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    errors = []
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    required = {"raw_goal", "goal_contract", "constraint", "success_criteria"}
    present = {n["type"] for n in nodes}
    missing = required - present
    if missing:
        errors.append(f"Missing required node types: {sorted(missing)}")

    ids = [n["id"] for n in nodes]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate node IDs detected")

    node_ids = set(ids)
    for e in edges:
        if e["source"] not in node_ids:
            errors.append(f"Edge source {e['source']} does not exist")
        if e["target"] not in node_ids:
            errors.append(f"Edge target {e['target']} does not exist")

    goal_contracts = [n for n in nodes if n.get("type") == "goal_contract"]
    if len(goal_contracts) != 1:
        errors.append(f"Expected exactly one goal_contract node, found {len(goal_contracts)}")
        return errors

    contract_id = goal_contracts[0]["id"]
    constraint_edges = [e for e in edges if e.get("source") == contract_id and e.get("type") == "constrains"]
    success_edges = [e for e in edges if e.get("source") == contract_id and e.get("type") == "requires_success"]
    seed_edges = [e for e in edges if e.get("source") == contract_id and e.get("type") == "generates_seed"]

    if not constraint_edges:
        errors.append("goal_contract must link to at least one constraint")
    if not success_edges:
        errors.append("goal_contract must link to at least one success_criteria")
    if not seed_edges:
        errors.append("goal_contract must generate a plan_seed")

    return errors
