import json
from pathlib import Path

REQUIRED_PROPERTIES = {"expected_outputs", "verifier_path", "tool_requirements", "risk_notes"}


def validate_plan_candidate(graph_path: str):
    """Validate Plan Candidate nodes.

    Checks:
    - At least two nodes of type "plan_candidate" exist.
    - Each candidate is linked from a "plan_seed" via an edge of type "expands_to_candidate".
    - Each candidate node's "properties" dict contains the required keys.
    """
    path = Path(graph_path)
    if not path.is_file():
        return [f"File not found: {graph_path}"]
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    errors = []
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    candidates = [n for n in nodes if n.get("type") == "plan_candidate"]
    if len(candidates) < 2:
        errors.append(f"Expected at least 2 plan_candidate nodes, found {len(candidates)}")

    # Map node id to node for quick lookup
    node_by_id = {n["id"]: n for n in nodes}
    # Verify each candidate has an incoming expands_to_candidate from a seed
    for cand in candidates:
        cand_id = cand["id"]
        incoming = [e for e in edges if e["target"] == cand_id and e["type"] == "expands_to_candidate"]
        if not incoming:
            errors.append(f"plan_candidate {cand_id} missing expands_to_candidate edge from a plan_seed")
        else:
            # Ensure source is a plan_seed
            src_id = incoming[0]["source"]
            src_node = node_by_id.get(src_id)
            if not src_node or src_node.get("type") != "plan_seed":
                    errors.append(f"plan_candidate {cand_id} expands_to_candidate edge source is not a plan_seed")
        # Check required properties
        props = cand.get("properties", {})
        missing = REQUIRED_PROPERTIES - set(props.keys())
        if missing:
            errors.append(f"plan_candidate {cand_id} missing required properties: {sorted(missing)}")

    return errors
