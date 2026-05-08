import json
from pathlib import Path

ALLOWED_EDGE_TYPES = {
    "generates_seed",
    "expands_to_candidate",
    "selected_as",
    "produces"
}


def validate_plan_seed(graph_path: str):
    """Validate the Plan Seed portion of a Plan Graph v1.

    Checks:
    - Exactly one node of type "plan_seed" exists.
    - It has an incoming edge from a "goal_contract" node with type "generates_seed".
    - It has at least one outgoing edge of type "expands_to_candidate".
    - It does NOT have outgoing edges of type "selected_as" or "produces" (i.e., no executable steps).
    """
    path = Path(graph_path)
    if not path.is_file():
        return [f"File not found: {graph_path}"]
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    errors = []
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    # Find plan_seed nodes
    seeds = [n for n in nodes if n.get("type") == "plan_seed"]
    if len(seeds) != 1:
        errors.append(f"Expected exactly one plan_seed node, found {len(seeds)}")
        return errors
    seed = seeds[0]
    seed_id = seed["id"]

    # Incoming edge from goal_contract with type generates_seed
    incoming = [e for e in edges if e["target"] == seed_id]
    if not any(e["type"] == "generates_seed" and any(n["id"] == e["source"] and n["type"] == "goal_contract" for n in nodes) for e in incoming):
        errors.append("plan_seed missing incoming generates_seed edge from a goal_contract")

    # Outgoing edges
    outgoing = [e for e in edges if e["source"] == seed_id]
    # Must have at least one expands_to_candidate
    if not any(e["type"] == "expands_to_candidate" for e in outgoing):
        errors.append("plan_seed must have at least one expands_to_candidate outgoing edge")
    # Must NOT have selected_as or produces edges
    for e in outgoing:
        if e["type"] in {"selected_as", "produces"}:
            errors.append(f"plan_seed has disallowed outgoing edge type {e['type']}")

    return errors
