#!/usr/bin/env python3
"""Tests for verification checkpoint and replanning loop."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agentic-pi" / "runtime"))


class TestVerificationCheckpoint(unittest.TestCase):
    """Test verification_checkpoint.py."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.run_dir = Path(self.tmpdir) / "test_run"
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_goal_contract(self, goal=None):
        """Write a goal_contract.json."""
        if goal is None:
            goal = {
                "run_id": "test_run",
                "goal_type": "coding",
                "raw_user_prompt": "Create a hello world script",
                "execution_prompt": "Create hello.py that prints 'Hello, World!'",
                "final_outputs": ["hello.py"],
            }
        (self.run_dir / "goal_contract.json").write_text(json.dumps(goal))

    def _write_plan_graph(self):
        """Write a plan_graph.json."""
        graph = {
            "nodes": [
                {"node_id": "T1", "type": "task", "task_id": "T1", "description": "create_file"},
                {"node_id": "A1", "type": "artifact", "artifact_id": "A1", "path": "hello.py"},
            ],
            "edges": [
                {"source": "T1", "target": "A1"},
            ],
        }
        (self.run_dir / "plan_graph.json").write_text(json.dumps(graph))

    def _write_step_logs(self):
        """Write step logs."""
        step_logs_dir = self.run_dir / "step_logs"
        step_logs_dir.mkdir(exist_ok=True)
        log = {
            "run_id": "test_run",
            "step_id": 1,
            "status": "PASSED",
            "action_taken": "create_file",
            "files_touched": ["hello.py"],
            "commands_run": [],
            "evidence": ["Created hello.py"],
            "pass_condition_satisfied": True,
            "remaining_work": [],
        }
        (step_logs_dir / "001.json").write_text(json.dumps(log))

    def test_no_goal_contract(self):
        """Test verification with no goal_contract.json."""
        from verification_checkpoint import run_verification_checkpoint
        feedback = run_verification_checkpoint(self.run_dir)
        self.assertFalse(feedback["has_gaps"] is False)
        self.assertIn("goal_contract", [c["check"] for c in feedback["checks"]])

    def test_valid_goal_contract(self):
        """Test verification with valid goal_contract.json."""
        from verification_checkpoint import run_verification_checkpoint
        self._write_goal_contract()
        feedback = run_verification_checkpoint(self.run_dir)
        goal_check = next(c for c in feedback["checks"] if c["check"] == "goal_contract")
        self.assertTrue(goal_check["passed"])

    def test_no_plan_graph(self):
        """Test verification with no plan_graph.json."""
        from verification_checkpoint import run_verification_checkpoint
        self._write_goal_contract()
        feedback = run_verification_checkpoint(self.run_dir)
        graph_check = next(c for c in feedback["checks"] if c["check"] == "plan_graph")
        self.assertFalse(graph_check["passed"])

    def test_valid_plan_graph(self):
        """Test verification with valid plan_graph.json."""
        from verification_checkpoint import run_verification_checkpoint
        self._write_goal_contract()
        self._write_plan_graph()
        feedback = run_verification_checkpoint(self.run_dir)
        graph_check = next(c for c in feedback["checks"] if c["check"] == "plan_graph")
        self.assertTrue(graph_check["passed"])

    def test_no_step_logs(self):
        """Test verification with no step logs."""
        from verification_checkpoint import run_verification_checkpoint
        self._write_goal_contract()
        self._write_plan_graph()
        feedback = run_verification_checkpoint(self.run_dir)
        step_check = next(c for c in feedback["checks"] if c["check"] == "step_logs")
        self.assertFalse(step_check["passed"])

    def test_valid_step_logs(self):
        """Test verification with valid step logs."""
        from verification_checkpoint import run_verification_checkpoint
        self._write_goal_contract()
        self._write_plan_graph()
        self._write_step_logs()
        feedback = run_verification_checkpoint(self.run_dir)
        step_check = next(c for c in feedback["checks"] if c["check"] == "step_logs")
        self.assertTrue(step_check["passed"])

    def test_all_checks_pass(self):
        """Test verification with all checks passing."""
        from verification_checkpoint import run_verification_checkpoint
        self._write_goal_contract()
        self._write_plan_graph()
        self._write_step_logs()
        # Write expected_artifacts.json
        (self.run_dir / "expected_artifacts.json").write_text(json.dumps({"artifacts": []}))
        # Write hello.py (output file)
        (self.run_dir / "hello.py").write_text("print('Hello, World!')")
        feedback = run_verification_checkpoint(self.run_dir)
        self.assertEqual(feedback["checks_passed"], feedback["checks_total"])
        self.assertFalse(feedback["has_gaps"])


class TestReplanningLoop(unittest.TestCase):
    """Test replanning_loop.py."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.run_dir = Path(self.tmpdir) / "test_run"
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_feedback(self, issues=None):
        """Write verification_feedback.json."""
        if issues is None:
            issues = []
        feedback = {
            "timestamp": "2026-05-29T00:00:00Z",
            "run_id": "test_run",
            "checks_passed": 5 - len(issues),
            "checks_total": 5,
            "checks": [],
            "issues": issues,
            "has_gaps": len(issues) > 0,
            "gap_summary": [i["issue"] for i in issues],
        }
        (self.run_dir / "verification_feedback.json").write_text(json.dumps(feedback))

    def _write_goal_contract(self):
        """Write a goal_contract.json."""
        goal = {
            "run_id": "test_run",
            "goal_type": "coding",
            "raw_user_prompt": "Create a hello world script",
        }
        (self.run_dir / "goal_contract.json").write_text(json.dumps(goal))

    def test_no_feedback(self):
        """Test replanning with no feedback."""
        from replanning_loop import run_replanning_loop
        result = run_replanning_loop(self.run_dir)
        self.assertFalse(result["needs_replanning"])

    def test_no_gaps(self):
        """Test replanning with no gaps."""
        from replanning_loop import run_replanning_loop
        self._write_feedback(issues=[])
        self._write_goal_contract()
        result = run_replanning_loop(self.run_dir)
        self.assertFalse(result["needs_replanning"])

    def test_with_gaps(self):
        """Test replanning with gaps."""
        from replanning_loop import run_replanning_loop
        issues = [
            {"check": "goal_contract", "passed": False, "issue": "missing fields"},
            {"check": "plan_graph", "passed": False, "issue": "no nodes"},
        ]
        self._write_feedback(issues=issues)
        self._write_goal_contract()
        result = run_replanning_loop(self.run_dir)
        self.assertTrue(result["needs_replanning"])
        self.assertEqual(len(result["actions"]), 2)

    def test_priority_ordering(self):
        """Test that actions are sorted by priority."""
        from replanning_loop import run_replanning_loop
        issues = [
            {"check": "step_logs", "passed": False, "issue": "no step logs"},
            {"check": "goal_contract", "passed": False, "issue": "missing fields"},
        ]
        self._write_feedback(issues=issues)
        self._write_goal_contract()
        result = run_replanning_loop(self.run_dir)
        # HIGH priority should come first
        self.assertEqual(result["actions"][0]["priority"], "HIGH")
        self.assertEqual(result["actions"][1]["priority"], "MEDIUM")


if __name__ == "__main__":
    unittest.main()
