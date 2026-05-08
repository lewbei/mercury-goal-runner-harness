import json
from pathlib import Path

class PlanGraphV1Builder:
    """Simple builder for the Plan Graph v1.

    It loads a JSON fixture that conforms to the schema and stores the
    nodes and edges in memory.  The builder does not perform any execution –
    it merely provides a convenient Python representation for validators and
    downstream tools.
    """

    def __init__(self, fixture_path: str):
        self.fixture_path = Path(fixture_path)
        self.graph = {"nodes": [], "edges": []}
        self._load()

    def _load(self):
        if not self.fixture_path.is_file():
            raise FileNotFoundError(f"Plan graph fixture not found: {self.fixture_path}")
        with self.fixture_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # Basic sanity – the validator will enforce the schema.
        self.graph["nodes"] = data.get("nodes", [])
        self.graph["edges"] = data.get("edges", [])

    def get_node(self, node_id: str):
        for n in self.graph["nodes"]:
            if n["id"] == node_id:
                return n
        return None

    def outgoing_edges(self, node_id: str):
        return [e for e in self.graph["edges"] if e["source"] == node_id]

    def incoming_edges(self, node_id: str):
        return [e for e in self.graph["edges"] if e["target"] == node_id]

    def all_nodes(self):
        return self.graph["nodes"]

    def all_edges(self):
        return self.graph["edges"]

    # Convenience for validators
    def node_types(self):
        return {n["type"] for n in self.graph["nodes"]}
