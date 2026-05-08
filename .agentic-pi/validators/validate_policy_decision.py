import json
from pathlib import Path

ALLOWED_STATUS = {"NOT_DONE", "PROVISIONAL_DONE", "CERTIFIED_DONE"}
ALLOWED_PROVENANCE = {"P0", "P1", "P2", "P3"}


def validate_policy_decision(graph_path: str):
    """Validate the Policy Decision portion of a Plan Graph v1.

    Checks:
    - Exactly one node of type "policy_decision" exists.
    - It must have a `verifier_ids` property (list of verifier_artifact IDs) and a `status` property.
    - All referenced verifier IDs must exist and be of type "verifier_artifact".
    - `status` must be one of the allowed values.
    - "CERTIFIED_DONE" is only allowed if at least one referenced verifier has provenance_level >= "P2" and strength == "certifying".
    """
    path = Path(graph_path)
    if not path.is_file():
        return [f"File not found: {graph_path}"]
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    errors = []
    nodes = data.get("nodes", [])
    node_by_id = {n["id"]: n for n in nodes}

    # Find policy decision node(s)
    pd_nodes = [n for n in nodes if n.get("type") == "policy_decision"]
    if len(pd_nodes) != 1:
        errors.append(f"Expected exactly one policy_decision node, found {len(pd_nodes)}")
        return errors
    pd = pd_nodes[0]
    props = pd.get("properties", {})

    # verifier_ids list
    verifier_ids = props.get("verifier_ids")
    if not isinstance(verifier_ids, list) or not verifier_ids:
        errors.append("policy_decision missing non‑empty 'verifier_ids' list")
    else:
        for vid in verifier_ids:
            if vid not in node_by_id:
                errors.append(f"policy_decision references unknown verifier id '{vid}'")
            elif node_by_id[vid].get("type") != "verifier_artifact":
                errors.append(f"policy_decision references node '{vid}' which is not a verifier_artifact")

    # status check
    status = props.get("status")
    if status not in ALLOWED_STATUS:
        errors.append(f"policy_decision has invalid status '{status}'. Allowed: {sorted(ALLOWED_STATUS)}")

    # Certification rule for CERTIFIED_DONE
    if status == "CERTIFIED_DONE":
        strong_ok = False
        for vid in verifier_ids:
            verifier_node = node_by_id.get(vid)
            if not verifier_node:
                continue
            vprops = verifier_node.get("properties", {})
            prov = vprops.get("provenance_level")
            strength = vprops.get("strength")
            if prov in {"P2", "P3"} and strength == "certifying":
                strong_ok = True
                break
        if not strong_ok:
            errors.append("CERTIFIED_DONE requires at least one verifier with provenance >= P2 and strength 'certifying'")

    return errors
