import json
from pathlib import Path


def validate_artifact_graph(graph_path: str):
    """Validate the Artifact Graph portion of a Plan Graph v1.

    Checks:
    - Every node of type "artifact" must have `path` and `hash` properties.
    - `path` must be a relative path (no leading '/' or '\\') and must not contain ".." components.
    - Each artifact must have exactly one incoming edge of type "produces" from a "task" node.
    - No two artifact nodes may declare the same `path` (duplicate output location).
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
    artifacts = [n for n in nodes if n.get("type") == "artifact"]
    tasks = {n["id"] for n in nodes if n.get("type") == "task"}

    # Track paths to detect duplicates
    seen_paths = set()

    for a in artifacts:
        aid = a["id"]
        props = a.get("properties", {})
        # path & hash existence
        p = props.get("path")
        h = props.get("hash")
        if not p:
            errors.append(f"Artifact {aid} missing 'path' property")
        else:
            # Relative path check
            if Path(p).is_absolute() or ".." in Path(p).parts:
                errors.append(f"Artifact {aid} has non‑relative or escaping path '{p}'")
            if p in seen_paths:
                errors.append(f"Duplicate artifact path '{p}' used by artifact {aid}")
            else:
                seen_paths.add(p)
        if not h:
            errors.append(f"Artifact {aid} missing 'hash' property")

        # Incoming produces edge count
        incoming = [e for e in edges if e["target"] == aid and e["type"] == "produces"]
        if len(incoming) != 1:
            errors.append(f"Artifact {aid} must have exactly one incoming 'produces' edge from a task, found {len(incoming)}")
        else:
            src = incoming[0]["source"]
            if src not in tasks:
                errors.append(f"Artifact {aid} produced by node {src} which is not a task")

    return errors
