#!/usr/bin/env python3
"""Tests for parallel execution."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agentic-pi" / "runtime"))


class TestParallelExecutor(unittest.TestCase):
    """Test parallel_executor.py."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.run_dir = Path(self.tmpdir) / "test_run"
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_plan_graph(self, nodes=None, edges=None):
        """Write plan_graph.json."""
        if nodes is None:
            nodes = [
                {"node_id": "T1", "type": "task", "task_id": "T1", "description": "task 1"},
                {"node_id": "T2", "type": "task", "task_id": "T2", "description": "task 2"},
                {"node_id": "T3", "type": "task", "task_id": "T3", "description": "task 3"},
                {"node_id": "A1", "type": "artifact", "artifact_id": "A1", "path": "file1.py"},
                {"node_id": "A2", "type": "artifact", "artifact_id": "A2", "path": "file2.py"},
            ]
        if edges is None:
            edges = [
                {"source": "T1", "target": "A1"},
                {"source": "T2", "target": "A2"},
            ]
        graph = {"nodes": nodes, "edges": edges}
        (self.run_dir / "plan_graph.json").write_text(json.dumps(graph))

    def test_empty_graph(self):
        """Test parallel executor with empty graph."""
        from parallel_executor import analyze_parallelism
        analysis = analyze_parallelism(self.run_dir)
        self.assertEqual(analysis["total_tasks"], 0)

    def test_independent_tasks(self):
        """Test parallel executor with independent tasks."""
        from parallel_executor import analyze_parallelism
        self._write_plan_graph()
        analysis = analyze_parallelism(self.run_dir)
        self.assertEqual(analysis["total_tasks"], 3)
        self.assertEqual(analysis["num_levels"], 1)  # All at level 0
        self.assertEqual(analysis["max_parallel"], 3)

    def test_dependent_tasks(self):
        """Test parallel executor with dependent tasks."""
        from parallel_executor import analyze_parallelism
        nodes = [
            {"node_id": "T1", "type": "task", "task_id": "T1"},
            {"node_id": "T2", "type": "task", "task_id": "T2"},
            {"node_id": "A1", "type": "artifact", "artifact_id": "A1"},
        ]
        edges = [
            {"source": "T1", "target": "A1"},
            {"source": "A1", "target": "T2"},
        ]
        self._write_plan_graph(nodes, edges)
        analysis = analyze_parallelism(self.run_dir)
        self.assertEqual(analysis["total_tasks"], 2)
        self.assertEqual(analysis["num_levels"], 2)  # T1 at level 0, T2 at level 1
        self.assertEqual(analysis["max_parallel"], 1)

    def test_parallelism_score(self):
        """Test parallelism score calculation."""
        from parallel_executor import analyze_parallelism
        # Fully parallel (all independent)
        self._write_plan_graph()
        analysis = analyze_parallelism(self.run_dir)
        self.assertEqual(analysis["parallelism_score"], 1.0)

    def test_execution_plan_generation(self):
        """Test execution plan generation."""
        from parallel_executor import analyze_parallelism, generate_execution_plan
        self._write_plan_graph()
        analysis = analyze_parallelism(self.run_dir)
        plan = generate_execution_plan(analysis)
        self.assertEqual(plan["total_levels"], 1)
        self.assertEqual(plan["total_tasks"], 3)
        self.assertTrue(plan["execution_plan"][0]["can_parallel"])

    def test_complex_graph(self):
        """Test with complex dependency graph."""
        from parallel_executor import analyze_parallelism
        nodes = [
            {"node_id": "T1", "type": "task", "task_id": "T1"},
            {"node_id": "T2", "type": "task", "task_id": "T2"},
            {"node_id": "T3", "type": "task", "task_id": "T3"},
            {"node_id": "T4", "type": "task", "task_id": "T4"},
            {"node_id": "A1", "type": "artifact", "artifact_id": "A1"},
            {"node_id": "A2", "type": "artifact", "artifact_id": "A2"},
        ]
        edges = [
            {"source": "T1", "target": "A1"},
            {"source": "T2", "target": "A2"},
            {"source": "A1", "target": "T3"},
            {"source": "A2", "target": "T3"},
            {"source": "T3", "target": "T4"},
        ]
        self._write_plan_graph(nodes, edges)
        analysis = analyze_parallelism(self.run_dir)
        self.assertEqual(analysis["total_tasks"], 4)
        # T1, T2 at level 0 (parallel), T3 at level 1, T4 at level 2
        self.assertEqual(analysis["num_levels"], 3)
        self.assertEqual(analysis["max_parallel"], 2)


if __name__ == "__main__":
    unittest.main()
