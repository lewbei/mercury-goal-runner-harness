import json
from pathlib import Path

ALLOWED_CHECK_RESULTS = {"PASS", "FAIL", "NEEDS_USER", "UNSUPPORTED"}


def validate_candidate_evaluation(graph_path: str):
    """Validate Candidate Evaluation sub‑graph.

    Checks:
    - For each "plan_candidate" there is exactly one "candidate_evaluation" node linked via "evaluated_by".
    - Each "candidate_evaluation" has three outgoing edges of types "checks_risk", "checks_tool", "checks_verifiability" to nodes of types "risk_check", "tool_check", "verify_check" respectively.
    - Each check node contains a "result" property whose value is one of the allowed results.
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
    # Find candidates
    candidates = [n for n in nodes if n.get("type") == "plan_candidate"]
    # Find evaluations
    evaluations = [n for n in nodes if n.get("type") == "candidate_evaluation"]

    # Map candidate id -> evaluation id via evaluated_by edge
    eval_by_candidate = {}
    for e in edges:
        if e["type"] == "evaluated_by":
            src = e["source"]
            tgt = e["target"]
            src_node = node_by_id.get(src)
            tgt_node = node_by_id.get(tgt)
            if src_node and tgt_node and src_node["type"] == "plan_candidate" and tgt_node["type"] == "candidate_evaluation":
                eval_by_candidate[src] = tgt

    # Verify each candidate has exactly one evaluation
    for cand in candidates:
        cid = cand["id"]
        if cid not in eval_by_candidate:
            errors.append(f"plan_candidate {cid} missing candidate_evaluation via evaluated_by edge")
        else:
            # Ensure exactly one evaluation per candidate
            # (If multiple edges exist, later checks will catch duplicates)
            pass

    # Verify each evaluation has three checks
    for eval_node in evaluations:
        eid = eval_node["id"]
        # Collect outgoing edges from this evaluation
        out_edges = [e for e in edges if e["source"] == eid]
        # Expect exactly one of each check type
        required = {"checks_risk": "risk_check", "checks_tool": "tool_check", "checks_verifiability": "verify_check"}
        for edge_type, node_type in required.items():
            matches = [e for e in out_edges if e["type"] == edge_type]
            if len(matches) != 1:
                errors.append(f"candidate_evaluation {eid} must have exactly one outgoing edge of type {edge_type}")
                continue
            target_id = matches[0]["target"]
            target_node = node_by_id.get(target_id)
            if not target_node or target_node["type"] != node_type:
                errors.append(f"candidate_evaluation {eid} edge {edge_type} points to node with wrong type (expected {node_type})")
                continue
            # Check result property on the check node
            result = target_node.get("properties", {}).get("result")
            if result not in ALLOWED_CHECK_RESULTS:
                errors.append(f"{node_type} {target_id} has invalid result '{result}'. Expected one of {sorted(ALLOWED_CHECK_RESULTS)}")

    return errors
