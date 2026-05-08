import json
from pathlib import Path


def validate_applicability_gate(graph_path: str):
    """Validate the Applicability Gate node and its connections.

    Checks:
    - Exactly one node of type "applicability_gate" exists.
    - Each "candidate_evaluation" node has an outgoing edge of type "evaluated_by" to the gate.
    - The gate has exactly one outgoing edge of type "selected_as" to a "selected_plan" node.
    - Any candidate that is not selected must have an outgoing edge of type "rejected_by" from the gate.
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
    evaluation_by_candidate = {}
    candidate_by_evaluation = {}
    check_results_by_evaluation = {}

    for edge in edges:
        if edge.get("type") == "evaluated_by":
            source = node_by_id.get(edge.get("source"))
            target = node_by_id.get(edge.get("target"))
            if source and target and source.get("type") == "plan_candidate" and target.get("type") == "candidate_evaluation":
                evaluation_by_candidate[source["id"]] = target["id"]
                candidate_by_evaluation[target["id"]] = source["id"]

    for eval_node in [n for n in nodes if n.get("type") == "candidate_evaluation"]:
        checks = {}
        for edge in [e for e in edges if e.get("source") == eval_node["id"]]:
            target = node_by_id.get(edge.get("target"))
            if not target:
                continue
            if edge.get("type") == "checks_risk" and target.get("type") == "risk_check":
                checks["risk"] = target.get("properties", {}).get("result")
                checks["risk_mitigation"] = target.get("properties", {}).get("mitigation")
            if edge.get("type") == "checks_tool" and target.get("type") == "tool_check":
                checks["tool"] = target.get("properties", {}).get("result")
            if edge.get("type") == "checks_verifiability" and target.get("type") == "verify_check":
                checks["verify"] = target.get("properties", {}).get("result")
        check_results_by_evaluation[eval_node["id"]] = checks
    # Find gate
    gates = [n for n in nodes if n.get("type") == "applicability_gate"]
    if len(gates) != 1:
        errors.append(f"Expected exactly one applicability_gate node, found {len(gates)}")
        return errors
    gate = gates[0]
    gate_id = gate["id"]

    # Ensure each candidate_evaluation points to the gate via evaluated_by
    evaluations = [n for n in nodes if n.get("type") == "candidate_evaluation"]
    for eval_node in evaluations:
        eval_id = eval_node["id"]
        # Look for edge eval -> gate with type evaluated_by
        match = [e for e in edges if e["source"] == eval_id and e["target"] == gate_id and e["type"] == "evaluated_by"]
        if not match:
            errors.append(f"candidate_evaluation {eval_id} missing evaluated_by edge to applicability_gate")

    # Gate -> selected_plan
    selected_edges = [e for e in edges if e["source"] == gate_id and e["type"] == "selected_as"]
    if len(selected_edges) != 1:
        errors.append(f"Applicability gate must have exactly one selected_as edge to a selected_plan, found {len(selected_edges)}")
    else:
        target_id = selected_edges[0]["target"]
        target_node = node_by_id.get(target_id)
        if not target_node or target_node["type"] != "selected_plan":
            errors.append(f"selected_as edge from gate points to node of wrong type (expected selected_plan)")
        else:
            selected_candidate_id = target_node.get("properties", {}).get("source_candidate_id")
            selection_reason = target_node.get("properties", {}).get("selection_reason")
            if not selected_candidate_id:
                errors.append("selected_plan must record source_candidate_id")
            elif selected_candidate_id not in evaluation_by_candidate:
                errors.append(f"selected_plan source_candidate_id {selected_candidate_id} is not a plan_candidate with evaluation")
            else:
                eval_id = evaluation_by_candidate[selected_candidate_id]
                checks = check_results_by_evaluation.get(eval_id, {})
                if checks.get("verify") == "FAIL":
                    errors.append("selected_plan cannot be selected when verify_check is FAIL")
                if checks.get("tool") == "UNSUPPORTED":
                    errors.append("selected_plan cannot be selected when tool_check is UNSUPPORTED")
                if checks.get("risk") == "FAIL" and not checks.get("risk_mitigation"):
                    errors.append("selected_plan cannot be selected when risk_check is FAIL without mitigation")
            if not selection_reason:
                errors.append("selected_plan must record selection_reason")

    # Gate -> rejected plans (optional, but if present must be of type rejected_by and point to plan_candidate)
    rejected_edges = [e for e in edges if e["source"] == gate_id and e["type"] == "rejected_by"]
    for e in rejected_edges:
        tgt = e["target"]
        tgt_node = node_by_id.get(tgt)
        if not tgt_node or tgt_node["type"] != "plan_candidate":
            errors.append(f"rejected_by edge from gate points to node of wrong type (expected plan_candidate)")
        elif not (
            e.get("properties", {}).get("reason")
            or tgt_node.get("properties", {}).get("rejection_reason")
        ):
            errors.append(f"rejected_by edge for plan_candidate {tgt} must include reason")

    return errors
