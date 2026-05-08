import json
from pathlib import Path


def validate_local_step_plan(graph_path: str):
    """Validate the Local Step Plan portion of a Plan Graph v1.

    Checks:
    - At least one node of type "local_step_plan" exists.
    - Each local_step_plan must have an incoming edge of type "decomposes_to" from a "milestone_plan".
    - Each local_step_plan must have an outgoing edge of type "compiles_to" to a "merged_plan" node.
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
    local_steps = [n for n in nodes if n.get("type") == "local_step_plan"]
    if not local_steps:
        errors.append("No local_step_plan nodes found")
        return errors

    # Check each local step
    for ls in local_steps:
        lid = ls["id"]
        # Incoming from milestone_plan via decomposes_to
        incoming = [e for e in edges if e["target"] == lid and e["type"] == "decomposes_to"]
        if not incoming:
            errors.append(f"local_step_plan {lid} missing incoming decomposes_to edge from a milestone_plan")
        else:
            src_id = incoming[0]["source"]
            src_node = node_by_id.get(src_id)
            if not src_node or src_node.get("type") != "milestone_plan":
                errors.append(f"local_step_plan {lid} incoming edge source is not a milestone_plan")

        # Outgoing to merged_plan via compiles_to
        outgoing = [e for e in edges if e["source"] == lid and e["type"] == "compiles_to"]
        if not outgoing:
            errors.append(f"local_step_plan {lid} missing outgoing compiles_to edge to a merged_plan")
        else:
            tgt_id = outgoing[0]["target"]
            tgt_node = node_by_id.get(tgt_id)
            if not tgt_node or tgt_node.get("type") != "merged_plan":
                errors.append(f"local_step_plan {lid} outgoing compiles_to target {tgt_id} is not a merged_plan")

    return errors
