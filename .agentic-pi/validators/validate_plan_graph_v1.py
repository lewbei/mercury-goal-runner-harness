import json
from pathlib import Path

ALLOWED_NODE_TYPES = {
    "raw_goal",
    "goal_contract",
    "constraint",
    "success_criteria",
    "plan_seed",
    "plan_candidate",
    "candidate_evaluation",
    "risk_check",
    "tool_check",
    "verify_check",
    "applicability_gate",
    "selected_plan",
    "milestone_plan",
    "local_step_plan",
    "merged_plan",
    "task",
    "artifact",
    "verifier_artifact",
    "policy_decision",
    "certification",
    "pi_report"
}

ALLOWED_EDGE_TYPES = {
    "defines",
    "constrains",
    "requires_success",
    "generates_seed",
    "expands_to_candidate",
    "evaluated_by",
    "checks_risk",
    "checks_tool",
    "checks_verifiability",
    "approved_by",
    "rejected_by",
    "selected_as",
    "decomposes_to",
    "compiles_to",
    "produces",
    "requires",
    "verifies",
    "judged_by",
    "certifies",
    "reported_by"
}

ALLOWED_TOP_LEVEL_FIELDS = {"nodes", "edges"}
ALLOWED_NODE_FIELDS = {"id", "type", "properties"}
ALLOWED_EDGE_FIELDS = {"source", "target", "type", "properties"}


def _node_by_id(nodes, node_id):
    for n in nodes:
        if n["id"] == node_id:
            return n
    return None


def validate_plan_graph(graph_path: str):
    """Validate a Plan Graph v1 JSON file.

    Returns a list of error strings.  An empty list means the graph is valid.
    """
    path = Path(graph_path)
    if not path.is_file():
        return [f"Graph file not found: {graph_path}"]
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    errors = []
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    if not isinstance(data, dict):
        return ["Plan graph must be a JSON object"]

    for key in data:
        if key not in ALLOWED_TOP_LEVEL_FIELDS:
            errors.append(f"Unexpected top-level field {key}")

    if not isinstance(nodes, list):
        errors.append("Field 'nodes' must be a list")
        nodes = []
    if not isinstance(edges, list):
        errors.append("Field 'edges' must be a list")
        edges = []

    for n in nodes:
        if not isinstance(n, dict):
            errors.append("Every node must be an object")
            continue
        for key in n:
            if key not in ALLOWED_NODE_FIELDS:
                errors.append(f"Node {n.get('id')} has unexpected field {key}")
        for key in ("id", "type"):
            if key not in n:
                errors.append(f"Node missing required field {key}")
        if n.get("type") not in ALLOWED_NODE_TYPES:
            errors.append(f"Node {n.get('id')} has disallowed type {n.get('type')}" )

    for e in edges:
        if not isinstance(e, dict):
            errors.append("Every edge must be an object")
            continue
        for key in e:
            if key not in ALLOWED_EDGE_FIELDS:
                errors.append(f"Edge {e.get('source')}->{e.get('target')} has unexpected field {key}")
        for key in ("source", "target", "type"):
            if key not in e:
                errors.append(f"Edge missing required field {key}")
        if e.get("type") not in ALLOWED_EDGE_TYPES:
            errors.append(f"Edge {e.get('source')}->{e.get('target')} has disallowed type {e.get('type')}" )

    # 3. Required node presence (minimal set)
    required = {"raw_goal", "goal_contract", "constraint", "success_criteria", "plan_seed"}
    present = {n["type"] for n in nodes}
    missing = required - present
    if missing:
        errors.append(f"Missing required node types: {sorted(missing)}")

    ids = [n["id"] for n in nodes if isinstance(n, dict) and "id" in n]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate node IDs detected")

    node_ids = set(ids)
    for e in edges:
        if not isinstance(e, dict):
            continue
        if "source" in e and e["source"] not in node_ids:
            errors.append(f"Edge source {e['source']} does not exist")
        if "target" in e and e["target"] not in node_ids:
            errors.append(f"Edge target {e['target']} does not exist")

    return errors
