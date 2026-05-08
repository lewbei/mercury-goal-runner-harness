import json
from pathlib import Path


def validate_milestone_plan(graph_path: str):
    """Validate the Milestone Plan portion of a Plan Graph v1.

    Checks:
    - Exactly one node of type "milestone_plan" exists.
    - It must have an incoming edge of type "decomposes_to" from a "selected_plan" node.
    - It must have at least one outgoing edge of type "decomposes_to" to a "local_step_plan" node.
    """
    path = Path(graph_path)
    if not path.is_file():
        return [f"File not found: {graph_path}"]
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    errors = []
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    node_by_id = {n["id"]: n for n in nodes}
    # Find milestone nodes
    milestones = [n for n in nodes if n.get("type") == "milestone_plan"]
    if len(milestones) != 1:
        errors.append(f"Expected exactly one milestone_plan node, found {len(milestones)}")
        return errors
    milestone = milestones[0]
    mid = milestone["id"]

    # Incoming edge from selected_plan via decomposes_to
    incoming = [e for e in edges if e["target"] == mid and e["type"] == "decomposes_to"]
    if not incoming:
        errors.append("milestone_plan missing incoming decomposes_to edge from a selected_plan")
    else:
        src_id = incoming[0]["source"]
        src_node = node_by_id.get(src_id)
        if not src_node or src_node.get("type") != "selected_plan":
            errors.append("milestone_plan incoming edge source is not a selected_plan")

    # Outgoing edges to local_step_plan
    outgoing = [e for e in edges if e["source"] == mid and e["type"] == "decomposes_to"]
    if not outgoing:
        errors.append("milestone_plan must have at least one outgoing decomposes_to edge to a local_step_plan")
    else:
        for e in outgoing:
            tgt_id = e["target"]
            tgt_node = node_by_id.get(tgt_id)
            if not tgt_node or tgt_node.get("type") != "local_step_plan":
                errors.append(f"milestone_plan outgoing edge {mid}->{tgt_id} does not target a local_step_plan")

    return errors
