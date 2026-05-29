#!/usr/bin/env python3
"""Tests for context management."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agentic-pi" / "runtime"))


class TestContextManager(unittest.TestCase):
    """Test context_manager.py."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.run_dir = Path(self.tmpdir) / "test_run"
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_file(self, path, content):
        """Write a file."""
        full_path = self.run_dir / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    def test_empty_run(self):
        """Test context manager with empty run directory."""
        from context_manager import run_context_manager
        summary = run_context_manager(self.run_dir)
        self.assertEqual(summary["usage"]["total_tokens"], 0)
        self.assertEqual(summary["usage"]["file_count"], 0)

    def test_with_goal_contract(self):
        """Test context manager with goal_contract.json."""
        from context_manager import run_context_manager
        self._write_file("goal_contract.json", json.dumps({"run_id": "test", "goal": "test goal"}))
        summary = run_context_manager(self.run_dir)
        self.assertGreater(summary["usage"]["total_tokens"], 0)
        self.assertEqual(summary["usage"]["file_count"], 1)

    def test_with_step_logs(self):
        """Test context manager with step logs."""
        from context_manager import run_context_manager
        self._write_file("goal_contract.json", json.dumps({"run_id": "test"}))
        self._write_file("step_logs/001.json", json.dumps({"step_id": 1, "status": "PASSED"}))
        self._write_file("step_logs/002.json", json.dumps({"step_id": 2, "status": "PASSED"}))
        summary = run_context_manager(self.run_dir)
        self.assertEqual(summary["usage"]["file_count"], 3)
        self.assertIn("step_log", summary["usage"]["by_category"])

    def test_with_artifacts(self):
        """Test context manager with artifacts."""
        from context_manager import run_context_manager
        self._write_file("goal_contract.json", json.dumps({"run_id": "test"}))
        self._write_file("artifacts/milestones/m1.md", "# Milestone 1")
        summary = run_context_manager(self.run_dir)
        self.assertIn("artifact", summary["usage"]["by_category"])

    def test_token_estimation(self):
        """Test token estimation."""
        from context_manager import estimate_tokens
        self.assertEqual(estimate_tokens("hello"), 1)  # 5 chars ≈ 1 token
        self.assertEqual(estimate_tokens("a" * 100), 25)  # 100 chars ≈ 25 tokens

    def test_recommendations_generated(self):
        """Test that recommendations are generated when needed."""
        from context_manager import run_context_manager
        # Create a large goal_contract.json to trigger recommendations
        large_content = json.dumps({"run_id": "test", "goal": "x" * 300000})
        self._write_file("goal_contract.json", large_content)
        summary = run_context_manager(self.run_dir)
        # Should have recommendations for large file
        self.assertTrue(len(summary["recommendations"]) > 0)

    def test_no_recommendations_small(self):
        """Test no recommendations for small context."""
        from context_manager import run_context_manager
        self._write_file("goal_contract.json", json.dumps({"run_id": "test"}))
        summary = run_context_manager(self.run_dir)
        # Should have no recommendations for small context
        self.assertEqual(len(summary["recommendations"]), 0)


if __name__ == "__main__":
    unittest.main()
