#!/usr/bin/env python3
"""Tests for long-horizon support."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agentic-pi" / "runtime"))


class TestLongHorizonManager(unittest.TestCase):
    """Test long_horizon_manager.py."""

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

    def _write_run_state(self, phase="IMPLEMENTING"):
        """Write run_state.json."""
        state = {
            "run_id": "test_run",
            "current_phase": phase,
            "phase_history": [{"phase": phase, "entered_at": "2026-05-29T00:00:00Z", "exited_at": None}],
        }
        self._write_file("run_state.json", json.dumps(state))

    def _write_merged_plan(self, steps=None):
        """Write merged_plan.json."""
        if steps is None:
            steps = [
                {"step_id": 1, "action": "create_file", "path": "file1.py"},
                {"step_id": 2, "action": "create_file", "path": "file2.py"},
                {"step_id": 3, "action": "create_file", "path": "file3.py"},
            ]
        self._write_file("merged_plan.json", json.dumps({"steps": steps}))

    def _write_step_logs(self, count=2):
        """Write step logs."""
        step_logs_dir = self.run_dir / "step_logs"
        step_logs_dir.mkdir(exist_ok=True)
        for i in range(1, count + 1):
            log = {
                "run_id": "test_run",
                "step_id": i,
                "status": "PASSED",
                "timestamp": f"2026-05-29T00:{i:02d}:00Z",
            }
            (step_logs_dir / f"{i}.json").write_text(json.dumps(log))

    def test_empty_run(self):
        """Test long-horizon manager with empty run directory."""
        from long_horizon_manager import run_long_horizon_manager
        result = run_long_horizon_manager(self.run_dir)
        self.assertEqual(result["status"], "NOT_STARTED")
        self.assertEqual(result["progress"]["total_steps"], 0)

    def test_with_plan_and_logs(self):
        """Test long-horizon manager with plan and step logs."""
        from long_horizon_manager import run_long_horizon_manager
        self._write_run_state()
        self._write_merged_plan()
        self._write_step_logs(2)
        result = run_long_horizon_manager(self.run_dir)
        self.assertEqual(result["status"], "IN_PROGRESS")
        self.assertEqual(result["progress"]["completed_steps"], 2)
        self.assertEqual(result["progress"]["total_steps"], 3)

    def test_completed(self):
        """Test long-horizon manager when all steps completed."""
        from long_horizon_manager import run_long_horizon_manager
        self._write_run_state()
        self._write_merged_plan()
        self._write_step_logs(3)
        result = run_long_horizon_manager(self.run_dir)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["progress"]["percentage"], 100.0)

    def test_failed(self):
        """Test long-horizon manager when step failed."""
        from long_horizon_manager import run_long_horizon_manager
        self._write_run_state()
        self._write_merged_plan()
        # Write a failed step log
        step_logs_dir = self.run_dir / "step_logs"
        step_logs_dir.mkdir(exist_ok=True)
        log = {"run_id": "test_run", "step_id": 1, "status": "FAILED"}
        (step_logs_dir / "1.json").write_text(json.dumps(log))
        result = run_long_horizon_manager(self.run_dir)
        self.assertEqual(result["status"], "FAILED")

    def test_checkpoint_creation(self):
        """Test checkpoint creation."""
        from long_horizon_manager import create_checkpoint, load_checkpoints
        self._write_run_state()
        checkpoint = create_checkpoint(self.run_dir, 1, "MILESTONE")
        self.assertIn("checkpoint_id", checkpoint)
        checkpoints = load_checkpoints(self.run_dir)
        self.assertEqual(len(checkpoints), 1)

    def test_last_checkpoint(self):
        """Test getting last checkpoint."""
        from long_horizon_manager import create_checkpoint, get_last_checkpoint
        self._write_run_state()
        create_checkpoint(self.run_dir, 1, "MILESTONE")
        create_checkpoint(self.run_dir, 2, "MILESTONE")
        last = get_last_checkpoint(self.run_dir)
        self.assertEqual(last["step_id"], 2)

    def test_progress_calculation(self):
        """Test progress calculation."""
        from long_horizon_manager import calculate_progress
        step_logs = [
            {"status": "PASSED"},
            {"status": "PASSED"},
            {"status": "FAILED"},
        ]
        progress = calculate_progress(step_logs, 5)
        self.assertEqual(progress["total_steps"], 5)
        self.assertEqual(progress["completed_steps"], 3)
        self.assertEqual(progress["passed_steps"], 2)
        self.assertEqual(progress["failed_steps"], 1)
        self.assertEqual(progress["remaining_steps"], 2)

    def test_eta_calculation(self):
        """Test ETA calculation."""
        from long_horizon_manager import calculate_eta
        progress = {"remaining_steps": 3}
        step_logs = [
            {"timestamp": "2026-05-29T00:00:00Z"},
            {"timestamp": "2026-05-29T00:01:00Z"},
        ]
        eta = calculate_eta(progress, step_logs)
        self.assertIsNotNone(eta["eta_seconds"])
        self.assertIn("m", eta["eta_human"])


if __name__ == "__main__":
    unittest.main()
