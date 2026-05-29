#!/usr/bin/env python3
"""Tests for research module and resume module."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agentic-pi" / "runtime"))


class TestResearchModule(unittest.TestCase):
    """Test research_module.py."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.run_dir = Path(self.tmpdir) / "test_run"
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_goal_contract(self):
        """Write a goal_contract.json."""
        goal = {
            "run_id": "test_run",
            "raw_user_prompt": "Build a todo app",
        }
        (self.run_dir / "goal_contract.json").write_text(json.dumps(goal))

    def test_get_current_date(self):
        """Test getting current date."""
        from research_module import get_current_date
        date_info = get_current_date()
        self.assertIn("date", date_info)
        self.assertIn("year", date_info)
        self.assertEqual(date_info["year"], 2026)

    def test_generate_research_context(self):
        """Test generating research context."""
        from research_module import generate_research_context
        self._write_goal_contract()
        context = generate_research_context(self.run_dir)
        self.assertIn("current_date", context)
        self.assertIn("model_search_queries", context)
        self.assertIn("technology_search_queries", context)

    def test_run_research(self):
        """Test running research."""
        from research_module import run_research
        self._write_goal_contract()
        result = run_research(self.run_dir)
        self.assertIn("current_date", result)
        # Check that research_context.json was written
        self.assertTrue((self.run_dir / "research_context.json").exists())


class TestResumeModule(unittest.TestCase):
    """Test resume_module.py."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.run_dir = Path(self.tmpdir) / "test_run"
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_run_state(self, phase="IMPLEMENTING"):
        """Write run_state.json."""
        state = {
            "run_id": "test_run",
            "current_phase": phase,
            "overall_status": "IN_PROGRESS",
            "created_at": "2026-05-29T00:00:00Z",
            "updated_at": "2026-05-29T00:01:00Z",
        }
        (self.run_dir / "run_state.json").write_text(json.dumps(state))

    def _write_goal_contract(self):
        """Write goal_contract.json."""
        goal = {
            "run_id": "test_run",
            "raw_user_prompt": "Build a todo app",
        }
        (self.run_dir / "goal_contract.json").write_text(json.dumps(goal))

    def _write_step_logs(self, count=2):
        """Write step logs."""
        step_logs_dir = self.run_dir / "step_logs"
        step_logs_dir.mkdir(exist_ok=True)
        for i in range(1, count + 1):
            log = {"step_id": i, "status": "PASSED"}
            (step_logs_dir / f"{i}.json").write_text(json.dumps(log))

    def test_list_runs_empty(self):
        """Test listing runs when empty."""
        # Monkey-patch RUNS_ROOT
        import resume_module
        original_root = resume_module.RUNS_ROOT
        resume_module.RUNS_ROOT = Path(self.tmpdir) / "empty_runs"
        resume_module.RUNS_ROOT.mkdir(exist_ok=True)
        
        runs = resume_module.list_runs()
        self.assertEqual(len(runs), 0)
        
        resume_module.RUNS_ROOT = original_root

    def test_list_runs_with_run(self):
        """Test listing runs with a run."""
        # Create a run directory in .agentic-runs
        runs_dir = Path(self.tmpdir) / ".agentic-runs"
        runs_dir.mkdir(exist_ok=True)
        run_dir = runs_dir / "test_run"
        run_dir.mkdir(parents=True)
        
        # Write run state
        state = {
            "run_id": "test_run",
            "current_phase": "IMPLEMENTING",
            "overall_status": "IN_PROGRESS",
            "created_at": "2026-05-29T00:00:00Z",
            "updated_at": "2026-05-29T00:01:00Z",
        }
        (run_dir / "run_state.json").write_text(json.dumps(state))
        
        # Write goal contract
        goal = {"run_id": "test_run", "raw_user_prompt": "Build a todo app"}
        (run_dir / "goal_contract.json").write_text(json.dumps(goal))
        
        # Monkey-patch RUNS_ROOT
        import resume_module
        original_root = resume_module.RUNS_ROOT
        resume_module.RUNS_ROOT = runs_dir
        
        runs = resume_module.list_runs()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["run_id"], "test_run")
        
        resume_module.RUNS_ROOT = original_root

    def test_get_resume_instructions(self):
        """Test getting resume instructions."""
        from resume_module import get_resume_instructions
        run = {
            "run_id": "test_run",
            "current_phase": "IMPLEMENTING",
            "step_count": 4,
            "goal": "Build a todo app",
        }
        instructions = get_resume_instructions(run)
        self.assertEqual(instructions["run_id"], "test_run")
        self.assertIn("command", instructions)


if __name__ == "__main__":
    unittest.main()
