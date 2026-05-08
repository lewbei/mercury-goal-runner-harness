import json
from pathlib import Path

ALLOWED_ACTIONS = {"run", "copy", "transform", "verify"}


def _detect_cycle(tasks, requires_edges):
    """Detect cycles in a directed graph defined by requires_edges.

    `tasks` is a set of task IDs.
    `requires_edges` is a list of (src, tgt) where src requires tgt.
    Returns True if a cycle is found, otherwise False.
    """
    # Build adjacency list: src -> list of tgt (src depends on tgt)
    adj = {t: [] for t in tasks}
    for src, tgt in requires_edges:
        if src in adj and tgt in adj:
            adj[src].append(tgt)

    visited = set()
    rec_stack = set()

    def dfs(v):
        visited.add(v)
        rec_stack.add(v)
        for neighbour in adj.get(v, []):
            if neighbour not in visited:
                if dfs(neighbour):
                    return True
            elif neighbour in rec_stack:
                return True
        rec_stack.remove(v)
        return False

    for node in tasks:
        if node not in visited:
            if dfs(node):
                return True
    return False


def validate_task_graph(graph_path: str):
    """Validate the Task Graph portion of a Plan Graph v1.

    Checks:
    - All nodes of type "task" have unique `task_id`.
    - Each task node has an `action` property from the allowed set.
    - Each task node has an `expected_artifact` property that references an existing "artifact" node.
    - All "artifact" nodes have `path` and `hash` properties.
    - Edge type "produces" must go from a task to an artifact.
    - Edge type "requires" must go from a task to another task (dependency).
    - No cycles in the dependency graph formed by "requires" edges.
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
    # Separate nodes by type
    tasks = [n for n in nodes if n.get("type") == "task"]
    artifacts = [n for n in nodes if n.get("type") == "artifact"]

    # --- Task checks ---
    task_ids = set()
    for t in tasks:
        props = t.get("properties", {})
        # task_id uniqueness
        tid = props.get("task_id")
        if not tid:
            errors.append(f"Task node {t['id']} missing 'task_id' property")
        else:
            if tid in task_ids:
                errors.append(f"Duplicate task_id '{tid}' in task node {t['id']}")
            else:
                task_ids.add(tid)
        # action check
        action = props.get("action")
        if action not in ALLOWED_ACTIONS:
            errors.append(f"Task node {t['id']} has invalid action '{action}'. Allowed: {sorted(ALLOWED_ACTIONS)}")
        # expected_artifact reference
        exp_art = props.get("expected_artifact")
        if not exp_art:
            errors.append(f"Task node {t['id']} missing 'expected_artifact' property")
        elif exp_art not in node_by_id:
            errors.append(f"Task node {t['id']} references unknown expected_artifact '{exp_art}'")
        elif node_by_id[exp_art].get("type") != "artifact":
            errors.append(f"Task node {t['id']} expected_artifact '{exp_art}' is not an artifact node")

    # --- Artifact checks ---
    for a in artifacts:
        props = a.get("properties", {})
        if "path" not in props:
            errors.append(f"Artifact node {a['id']} missing 'path' property")
        if "hash" not in props:
            errors.append(f"Artifact node {a['id']} missing 'hash' property")

    # --- Edge checks ---
    requires_edges = []
    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        etype = e.get("type")
        if src not in node_by_id or tgt not in node_by_id:
            errors.append(f"Edge {src}->{tgt} references unknown node(s)")
            continue
        src_node = node_by_id[src]
        tgt_node = node_by_id[tgt]
        if etype == "produces":
            if src_node.get("type") != "task" or tgt_node.get("type") != "artifact":
                errors.append(f"produces edge {src}->{tgt} must go from task to artifact")
        elif etype == "requires":
            if src_node.get("type") != "task" or tgt_node.get("type") != "task":
                errors.append(f"requires edge {src}->{tgt} must go from task to task")
            else:
                requires_edges.append((src, tgt))
        else:
            # other edge types are allowed in the broader graph, ignore here
            pass

    # --- Cycle detection ---
    task_ids_set = {t.get("id") for t in tasks}
    if _detect_cycle(task_ids_set, requires_edges):
        errors.append("Cycle detected in task dependency graph (requires edges)")

    return errors
