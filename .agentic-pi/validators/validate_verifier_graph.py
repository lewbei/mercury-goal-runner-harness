import json
from pathlib import Path

ALLOWED_PROVENANCE = {"P0", "P1", "P2", "P3"}
ALLOWED_STRENGTH = {"weak", "advisory", "gating", "certifying"}


def validate_verifier_graph(graph_path: str):
    """Validate the Verifier Graph portion of a Plan Graph v1.

    Checks:
    - Every node of type "verifier_artifact" must have properties:
        * `target_artifact` (id of an existing artifact node)
        * `provenance_level` (one of P0‑P3)
        * `strength` (weak, advisory, gating, or certifying)
    - Edge type "verifies" must go from a verifier_artifact to an artifact.
    - Each artifact that is a final output should have at least one verifier_artifact.
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
    artifacts = {n["id"]: n for n in nodes if n.get("type") == "artifact"}
    verifiers = [n for n in nodes if n.get("type") == "verifier_artifact"]

    # Validate each verifier node
    for v in verifiers:
        vid = v["id"]
        props = v.get("properties", {})
        target = props.get("target_artifact")
        prov = props.get("provenance_level")
        strength = props.get("strength")
        if not target:
            errors.append(f"Verifier {vid} missing 'target_artifact' property")
        elif target not in artifacts:
            errors.append(f"Verifier {vid} references unknown artifact '{target}'")
        if prov not in ALLOWED_PROVENANCE:
            errors.append(f"Verifier {vid} has invalid provenance_level '{prov}'. Allowed: {sorted(ALLOWED_PROVENANCE)}")
        if strength not in ALLOWED_STRENGTH:
            errors.append(f"Verifier {vid} has invalid strength '{strength}'. Allowed: {sorted(ALLOWED_STRENGTH)}")

    # Edge checks
    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        etype = e.get("type")
        if etype == "verifies":
            # source must be verifier_artifact, target must be artifact
            src_node = node_by_id.get(src)
            tgt_node = node_by_id.get(tgt)
            if not src_node or src_node.get("type") != "verifier_artifact":
                errors.append(f"verifies edge source {src} is not a verifier_artifact")
            if not tgt_node or tgt_node.get("type") != "artifact":
                errors.append(f"verifies edge target {tgt} is not an artifact")

    artifact_with_verifier = {e["target"] for e in edges if e.get("type") == "verifies"}
    final_artifacts = [
        n for n in artifacts.values()
        if n.get("properties", {}).get("final_output") is True
    ]
    for artifact in final_artifacts:
        if artifact["id"] not in artifact_with_verifier:
            errors.append(f"Final artifact {artifact['id']} has no verifier_artifact")

    return errors
