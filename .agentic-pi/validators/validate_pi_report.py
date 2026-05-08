import json
from pathlib import Path


def validate_pi_report(graph_path: str):
    """Validate the Pi Report portion of a Plan Graph v1.

    Checks:
    - Exactly one node of type "pi_report" exists.
    - It must have an incoming edge of type "reported_by" from a "certification" node.
    - The pi_report node must NOT have any outgoing edge of type "certifies" (it cannot certify).
    - The pi_report node must not contain any property that attempts to modify status (e.g., a "status" property).
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
    # Find pi_report node
    reports = [n for n in nodes if n.get("type") == "pi_report"]
    if len(reports) != 1:
        errors.append(f"Expected exactly one pi_report node, found {len(reports)}")
        return errors
    report = reports[0]
    rid = report["id"]

    # Incoming reported_by from certification
    incoming = [e for e in edges if e["target"] == rid and e["type"] == "reported_by"]
    if not incoming:
        errors.append("pi_report missing incoming reported_by edge from a certification node")
    else:
        src_id = incoming[0]["source"]
        src_node = node_by_id.get(src_id)
        if not src_node or src_node.get("type") != "certification":
            errors.append("pi_report incoming reported_by edge source is not a certification node")

    # Ensure no outgoing certifies edge
    outgoing_cert = [e for e in edges if e["source"] == rid and e["type"] == "certifies"]
    if outgoing_cert:
        errors.append("pi_report must not have any outgoing certifies edges")

    # Disallow status property on pi_report
    props = report.get("properties", {})
    if "status" in props:
        errors.append("pi_report must not contain a 'status' property (cannot upgrade status)")
    if props.get("claims_certification") is True:
        errors.append("pi_report must not claim certification authority")
    if props.get("inferred_missing_status") is True:
        errors.append("pi_report must not infer status from missing certifier artifacts")
    command = str(props.get("command", ""))
    normalized_command = command.lower().replace("^", "").replace("`", "")
    if "final_status.md" in normalized_command and any(token in normalized_command for token in ["set-content", "echo", "out-file", "write"]):
        errors.append("pi_report contains command that attempts to write final_status.md")

    return errors
