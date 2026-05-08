import json
from pathlib import Path


def validate_merged_plan(graph_path: str):
    """Validate the Merged Plan portion of a Plan Graph v1.

    Checks:
    - Exactly one node of type "merged_plan" exists.
    - It must have incoming edges of type "compiles_to" from each "local_step_plan" node.
    - It must have outgoing edges of type "decomposes_to" to "task" nodes (the task graph).
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
    # Find merged_plan node
    merged_nodes = [n for n in nodes if n.get("type") == "merged_plan"]
    if len(merged_nodes) != 1:
        errors.append(f"Expected exactly one merged_plan node, found {len(merged_nodes)}")
        return errors
    merged = merged_nodes[0]
    mid = merged["id"]

    # Incoming compiles_to from local_step_plan
    incoming = [e for e in edges if e["target"] == mid and e["type"] == "compiles_to"]
    if not incoming:
        errors.append("merged_plan missing incoming compiles_to edges from local_step_plan nodes")
    else:
        for e in incoming:
            src_id = e["source"]
            src_node = node_by_id.get(src_id)
            if not src_node or src_node.get("type") != "local_step_plan":
                errors.append(f"merged_plan incoming edge source {src_id} is not a local_step_plan")

    # Outgoing decomposes_to to task nodes
    outgoing = [e for e in edges if e["source"] == mid and e["type"] == "decomposes_to"]
    if not outgoing:
        errors.append("merged_plan missing outgoing decomposes_to edges to task nodes")
    else:
        for e in outgoing:
            tgt_id = e["target"]
            tgt_node = node_by_id.get(tgt_id)
            if not tgt_node or tgt_node.get("type") != "task":
                errors.append(f"merged_plan outgoing edge target {tgt_id} is not a task node")

    return errors
