#!/usr/bin/env python3
"""Merge selected plan(s) into a unified execution plan.

Usage:
    python .agentic-pi/runtime/plan_merger.py --run-id <run_id>
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

#@ Requires(lambda path: isinstance(path, Path) and path.is_file(), "selected_plan.json must exist")
#@ Ensures(lambda result: isinstance(result, dict), "selected_plan must be a dict")
def load_json(path: Path) -> Dict[str, Any]:
    """Load a JSON file and return its content as a dict."""
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)

#@ Requires(lambda graph: isinstance(graph, dict), "graph must be a dict")
#@ Ensures(lambda result: isinstance(result, dict), "normalized graph must be a dict")
def normalize_graph(graph: Dict[str, Any]) -> Dict[str, Any]:
    """Convert legacy keys to the unified schema.

    Nodes: `id` -> `node_id`
    Edges: `from`/`to` -> `source`/`target`
    """
    normalized: Dict[str, Any] = {'nodes': [], 'edges': []}
    # Normalize nodes
    for node in graph.get('nodes', []):
        new_node = dict(node)  # shallow copy
        if 'id' in new_node:
            new_node['node_id'] = new_node.pop('id')
        normalized['nodes'].append(new_node)
    # Normalize edges
    for edge in graph.get('edges', []):
        new_edge = dict(edge)
        if 'from' in new_edge:
            new_edge['source'] = new_edge.pop('from')
        if 'to' in new_edge:
            new_edge['target'] = new_edge.pop('to')
        normalized['edges'].append(new_edge)
    return normalized

#@ Requires(lambda primary, secondary: isinstance(primary, dict) and isinstance(secondary, dict), "both graphs must be dicts")
#@ Ensures(lambda result: isinstance(result, dict), "merged graph must be a dict")
def choose_primary_graph(primary: Dict[str, Any], secondary: Dict[str, Any]) -> Dict[str, Any]:
    """Return the graph with the greater number of nodes. If equal, return primary."""
    if len(primary.get('nodes', [])) >= len(secondary.get('nodes', [])):
        return primary
    return secondary

def main() -> None:
    parser = argparse.ArgumentParser(description="Merge selected plan(s) for a run")
    parser.add_argument("--run-id", required=True, help="Run identifier")
    args = parser.parse_args()
    run_dir = Path('.agentic-runs') / args.run_id
    # 1. Load selected plan metadata
    selected_path = run_dir / 'selected_plan.json'
    selected_plan = load_json(selected_path)
    # Determine which thinking plan file to use
    plan_name = selected_plan.get('selected_plan', '')
    # Fallback to default if key missing
    if not plan_name:
        plan_name = 'thinking_plan.md'
    # Resolve thinking plan path (allow minimal variant)
    thinking_path = run_dir / (plan_name if plan_name.endswith('.md') else 'thinking_plan.md')
    if not thinking_path.is_file():
        # Try minimal variant
        thinking_path = run_dir / (plan_name.replace('.md', '_minimal.md'))
    with thinking_path.open('r', encoding='utf-8') as f:
        thinking_content = f.read()

    # 2. Load both graph variants
    robust_path = run_dir / 'plan_graph.json'
    minimal_path = run_dir / 'plan_graph_minimal.json'
    robust_graph = load_json(robust_path)
    minimal_graph = load_json(minimal_path)

    # 3. Normalize both graphs
    robust_norm = normalize_graph(robust_graph)
    minimal_norm = normalize_graph(minimal_graph)

    # 4. Choose primary graph (more nodes)
    primary_graph = choose_primary_graph(robust_norm, minimal_norm)

    # 5. Assemble final merged structure
    merged = {
        'nodes': primary_graph['nodes'],
        'edges': primary_graph['edges'],
        'thinking_plan': thinking_content,
        'selected_plan_metadata': selected_plan
    }

    # 6. Write merged_plan_final.json
    merged_path = run_dir / 'merged_plan_final.json'
    with merged_path.open('w', encoding='utf-8') as f:
        json.dump(merged, f, indent=2)

    # 7. Output confirmation (2+ lines)
    print(f"Merged plan written to {merged_path}")
    print(f"Primary graph contains {len(merged['nodes'])} nodes and {len(merged['edges'])} edges.")

if __name__ == '__main__':
    main()
