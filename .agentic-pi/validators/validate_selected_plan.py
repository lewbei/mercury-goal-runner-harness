import json
from pathlib import Path


def validate_selected_plan(graph_path: str):
    """Validate the Selected Plan node.

    Checks:
    - Exactly one node of type "selected_plan" exists.
    - It has an incoming edge of type "selected_as" from an "applicability_gate" node.
    - It has an outgoing edge of type "requires_success" to a "success_criteria" node.
    - It does NOT have any outgoing edge of type "certifies" (selected plan cannot certify).
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

    selected = [n for n in nodes if n.get("type") == "selected_plan"]
    if len(selected) != 1:
        errors.append(f"Expected exactly one selected_plan node, found {len(selected)}")
        return errors
    sel_node = selected[0]
    sel_id = sel_node["id"]
    props = sel_node.get("properties", {})
    source_candidate_id = props.get("source_candidate_id")
    if not source_candidate_id:
        errors.append("selected_plan must record source_candidate_id")
    elif source_candidate_id not in node_by_id or node_by_id[source_candidate_id].get("type") != "plan_candidate":
        errors.append("selected_plan source_candidate_id must point to a plan_candidate")
    if not props.get("selection_reason"):
        errors.append("selected_plan must record selection_reason")

    # Incoming selected_as from applicability_gate
    incoming = [e for e in edges if e["target"] == sel_id and e["type"] == "selected_as"]
    if len(incoming) != 1:
        errors.append("selected_plan must have exactly one incoming selected_as edge from an applicability_gate")
    else:
        src_id = incoming[0]["source"]
        src_node = node_by_id.get(src_id)
        if not src_node or src_node["type"] != "applicability_gate":
            errors.append("selected_plan incoming selected_as edge source is not an applicability_gate")

    # Outgoing requires_success to success_criteria
    outgoing = [e for e in edges if e["source"] == sel_id]
    success_edges = [e for e in outgoing if e["type"] == "requires_success"]
    if len(success_edges) != 1:
        errors.append("selected_plan must have exactly one outgoing requires_success edge to a success_criteria")
    else:
        tgt_id = success_edges[0]["target"]
        tgt_node = node_by_id.get(tgt_id)
        if not tgt_node or tgt_node["type"] != "success_criteria":
            errors.append("selected_plan requires_success edge points to node of wrong type (expected success_criteria)")

    # Ensure no certifies edge
    cert_edges = [e for e in outgoing if e["type"] == "certifies"]
    if cert_edges:
        errors.append("selected_plan must not have any outgoing certifies edges")

    return errors
