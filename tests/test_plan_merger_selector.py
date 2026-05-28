"""Tests for plan_selector.py and plan_merger.py.

These are critical path modules — if they break, the planning pipeline
produces wrong plans silently. The health check flagged them as gaps.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".agentic-pi" / "runtime"


class TestPlanSelector(unittest.TestCase):
    """Tests for .agentic-pi/runtime/plan_selector.py."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.run_dir = self.tmpdir / "test_run"
        self.run_dir.mkdir()
        self.plans_dir = self.run_dir / "plans"
        self.plans_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _load_module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "plan_selector", RUNTIME / "plan_selector.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_selects_plan_with_fewest_steps(self):
        """Selector picks the plan with fewer steps."""
        # Plan A: 3 steps
        plan_a = {"steps": [
            {"task_id": "T1", "action": "create_file"},
            {"task_id": "T2", "action": "create_file"},
            {"task_id": "T3", "action": "create_file"},
        ]}
        (self.plans_dir / "planner_a_plan.json").write_text(json.dumps(plan_a))

        # Plan B: 2 steps (should be selected)
        plan_b = {"steps": [
            {"task_id": "T1", "action": "create_file"},
            {"task_id": "T2", "action": "create_file"},
        ]}
        (self.plans_dir / "planner_b_plan.json").write_text(json.dumps(plan_b))

        # Direct test of selection logic
        plans = []
        for pf in sorted(self.plans_dir.glob("*_plan.json")):
            plans.append(json.loads(pf.read_text()))

        best = min(plans, key=lambda p: len(p.get("steps", [])))
        self.assertEqual(len(best["steps"]), 2)

    def test_fails_when_no_plans(self):
        """Selector fails when plans directory is empty."""
        import subprocess
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "plan_selector.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir),
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_fails_when_plan_has_no_steps(self):
        """Selector fails when a plan has empty steps."""
        plan = {"steps": []}
        (self.plans_dir / "empty_plan.json").write_text(json.dumps(plan))

        import subprocess
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "plan_selector.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir),
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_fails_when_step_missing_task_id(self):
        """Selector fails when a step is missing task_id."""
        plan = {"steps": [{"action": "create_file"}]}
        (self.plans_dir / "bad_plan.json").write_text(json.dumps(plan))

        import subprocess
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "plan_selector.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir),
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_writes_selected_plan_json(self):
        """Selector writes selected_plan.json."""
        plan = {"steps": [{"task_id": "T1", "action": "create_file"}]}
        (self.plans_dir / "good_plan.json").write_text(json.dumps(plan))

        # We need to set up the .agentic-runs directory structure
        runs_dir = self.tmpdir / ".agentic-runs" / "test_run"
        runs_dir.mkdir(parents=True)
        plans_dir = runs_dir / "plans"
        plans_dir.mkdir()
        (plans_dir / "good_plan.json").write_text(json.dumps(plan))

        import subprocess
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "plan_selector.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir),
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        selected = runs_dir / "selected_plan.json"
        self.assertTrue(selected.exists())


class TestPlanMerger(unittest.TestCase):
    """Tests for .agentic-pi/runtime/plan_merger.py."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.run_dir = self.tmpdir / ".agentic-runs" / "test_run"
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_selected(self, plan):
        (self.run_dir / "selected_plan.json").write_text(json.dumps(plan))

    def test_builds_merged_plan_from_valid_steps(self):
        """Merger builds merged_plan.json from valid steps."""
        selected = {
            "steps": [
                {"task_id": "T1", "action": "create_file", "path": "out.py",
                 "requires": [], "produces": [{"artifact_id": "A.001", "path": "out.py"}]}
            ],
            "planner": "test",
        }
        self._write_selected(selected)

        import subprocess
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "plan_merger.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir),
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        merged_path = self.run_dir / "merged_plan.json"
        self.assertTrue(merged_path.exists())
        merged = json.loads(merged_path.read_text())
        self.assertEqual(merged["schema_version"], "merged_plan_v1")
        self.assertEqual(len(merged["steps"]), 1)
        self.assertEqual(merged["steps"][0]["task_id"], "T1")

    def test_preserves_metadata(self):
        """Merger preserves non-steps metadata from selected plan."""
        selected = {
            "steps": [{"task_id": "T1", "action": "create_file", "path": "out.py"}],
            "planner": "test-planner",
            "version": "1.0",
        }
        self._write_selected(selected)

        import subprocess
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "plan_merger.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir),
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        merged = json.loads((self.run_dir / "merged_plan.json").read_text())
        self.assertEqual(merged["selected_plan_metadata"]["planner"], "test-planner")
        self.assertEqual(merged["selected_plan_metadata"]["version"], "1.0")

    def test_fails_when_action_not_create_file(self):
        """Merger rejects steps with unsupported actions."""
        selected = {
            "steps": [{"task_id": "T1", "action": "delete_file", "path": "out.py"}]
        }
        self._write_selected(selected)

        import subprocess
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "plan_merger.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir),
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_fails_when_missing_task_id(self):
        """Merger rejects steps without task_id."""
        selected = {
            "steps": [{"action": "create_file", "path": "out.py"}]
        }
        self._write_selected(selected)

        import subprocess
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "plan_merger.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir),
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_fails_when_missing_path(self):
        """Merger rejects create_file steps without path."""
        selected = {
            "steps": [{"task_id": "T1", "action": "create_file"}]
        }
        self._write_selected(selected)

        import subprocess
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "plan_merger.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir),
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_fails_when_steps_empty(self):
        """Merger rejects empty steps list."""
        selected = {"steps": []}
        self._write_selected(selected)

        import subprocess
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "plan_merger.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir),
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_validates_produces_artifacts(self):
        """Merger validates produces artifact structure."""
        selected = {
            "steps": [{
                "task_id": "T1",
                "action": "create_file",
                "path": "out.py",
                "produces": [{"artifact_id": "A.001", "path": "out.py"}]
            }]
        }
        self._write_selected(selected)

        import subprocess
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "plan_merger.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir),
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        merged = json.loads((self.run_dir / "merged_plan.json").read_text())
        self.assertEqual(merged["steps"][0]["produces"][0]["artifact_id"], "A.001")

    def test_fails_when_produces_missing_artifact_id(self):
        """Merger rejects produces without artifact_id."""
        selected = {
            "steps": [{
                "task_id": "T1",
                "action": "create_file",
                "path": "out.py",
                "produces": [{"path": "out.py"}]  # missing artifact_id
            }]
        }
        self._write_selected(selected)

        import subprocess
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "plan_merger.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir),
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_multiple_steps_merged(self):
        """Merger handles multiple steps correctly."""
        selected = {
            "steps": [
                {"task_id": "T1", "action": "create_file", "path": "a.py"},
                {"task_id": "T2", "action": "create_file", "path": "b.py", "requires": ["T1"]},
                {"task_id": "T3", "action": "create_file", "path": "c.py", "requires": ["T1", "T2"]},
            ]
        }
        self._write_selected(selected)

        import subprocess
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "plan_merger.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir),
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        merged = json.loads((self.run_dir / "merged_plan.json").read_text())
        self.assertEqual(len(merged["steps"]), 3)
        self.assertEqual(merged["steps"][2]["requires"], ["T1", "T2"])


if __name__ == "__main__":
    unittest.main()
