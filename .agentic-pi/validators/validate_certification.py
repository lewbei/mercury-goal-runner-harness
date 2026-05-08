import json
from pathlib import Path

ALLOWED_STATUS = {"NOT_DONE", "PROVISIONAL_DONE", "CERTIFIED_DONE"}


def validate_certification(graph_path: str):
    """Validate the Certification portion of a Plan Graph v1.

    Checks:
    - Exactly one node of type "certification" exists.
    - It must have properties:
        * `policy_decision_id` (id of a policy_decision node)
        * `status` (one of the allowed statuses)
        * `final_status_path` (relative path, no "..")
        * `certification_json_path` (relative path, no "..")
    - The referenced policy_decision must exist.
    - Certification status may not exceed the status of the referenced policy_decision (e.g., a policy with NOT_DONE cannot have a CERTIFIED_DONE certification).
    """
    path = Path(graph_path)
    if not path.is_file():
        return [f"File not found: {graph_path}"]
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    errors = []
    nodes = data.get("nodes", [])
    node_by_id = {n["id"]: n for n in nodes}

    cert_nodes = [n for n in nodes if n.get("type") == "certification"]
    if len(cert_nodes) != 1:
        errors.append(f"Expected exactly one certification node, found {len(cert_nodes)}")
        return errors
    cert = cert_nodes[0]
    props = cert.get("properties", {})

    # policy_decision_id
    pid = props.get("policy_decision_id")
    if not pid:
        errors.append("certification missing 'policy_decision_id' property")
    elif pid not in node_by_id:
        errors.append(f"certification references unknown policy_decision_id '{pid}'")
    elif node_by_id[pid].get("type") != "policy_decision":
        errors.append(f"certification references node '{pid}' which is not a policy_decision")

    # status
    status = props.get("status")
    if status not in ALLOWED_STATUS:
        errors.append(f"certification has invalid status '{status}'. Allowed: {sorted(ALLOWED_STATUS)}")

    # final_status_path and certification_json_path checks
    for key in ["final_status_path", "certification_json_path"]:
        p = props.get(key)
        if not p:
            errors.append(f"certification missing '{key}' property")
        else:
            # Must be a relative path without escaping
            if Path(p).is_absolute() or ".." in Path(p).parts:
                errors.append(f"certification {key} '{p}' is not a safe relative path")
    if props.get("final_status_path") != "final_status.md":
        errors.append("certification final_status_path must be the certifier-owned final_status.md")
    if props.get("certification_json_path") not in {"certification.json", "cert.json"}:
        errors.append("certification_json_path must point to the certifier-owned certification JSON")

    # If policy decision exists, compare statuses
    if pid and pid in node_by_id and node_by_id[pid].get("type") == "policy_decision":
        policy_node = node_by_id[pid]
        policy_status = policy_node.get("properties", {}).get("status")
        # Simple ordering: NOT_DONE < PROVISIONAL_DONE < CERTIFIED_DONE
        order = {"NOT_DONE": 0, "PROVISIONAL_DONE": 1, "CERTIFIED_DONE": 2}
        if policy_status in order and status in order:
            if order[status] > order[policy_status]:
                errors.append(f"certification status '{status}' exceeds policy_decision status '{policy_status}'")

    return errors
