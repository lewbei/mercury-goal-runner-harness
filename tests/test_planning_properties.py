"""Property-based tests for the planning system.

Metamorphic properties:
  1. If the plan changes, the merged plan should change
  2. If the input is invalid, the plan should be rejected
  3. If the steps are reordered, the merged plan preserves order
  4. If a step is missing required fields, validation fails
  5. If the goal contract changes, the planning artifacts should change
"""
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".agentic-pi" / "runtime"


class TestPlanningProperties(unittest.TestCase):
    """Metamorphic properties for the planning system."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.run_dir = self.tmpdir / ".agentic-runs" / "test_run"
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_selected(self, plan):
        (self.run_dir / "selected_plan.json").write_text(json.dumps(plan))

    def _run_merger(self):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "plan_merger.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir), capture_output=True, text=True,
        )
        return result

    def _read_merged(self):
        return json.loads((self.run_dir / "merged_plan.json").read_text())

    # ── Property 1: Plan change → merged plan change ──────────────────

    def test_different_plans_produce_different_merged(self):
        """If the selected plan changes, the merged plan should change."""
        plan_a = {"steps": [{"task_id": "T1", "action": "create_file", "path": "a.py"}]}
        plan_b = {"steps": [{"task_id": "T2", "action": "create_file", "path": "b.py"}]}

        self._write_selected(plan_a)
        self._run_merger()
        merged_a = self._read_merged()

        self._write_selected(plan_b)
        self._run_merger()
        merged_b = self._read_merged()

        self.assertNotEqual(merged_a["steps"][0]["task_id"], merged_b["steps"][0]["task_id"])

    # ── Property 2: Invalid input → rejection ─────────────────────────

    def test_missing_task_id_rejected(self):
        """Steps without task_id should be rejected."""
        plan = {"steps": [{"action": "create_file", "path": "out.py"}]}
        self._write_selected(plan)
        result = self._run_merger()
        self.assertNotEqual(result.returncode, 0)

    def test_invalid_action_rejected(self):
        """Steps with unsupported actions should be rejected."""
        plan = {"steps": [{"task_id": "T1", "action": "delete_file", "path": "out.py"}]}
        self._write_selected(plan)
        result = self._run_merger()
        self.assertNotEqual(result.returncode, 0)

    def test_empty_steps_rejected(self):
        """Empty steps list should be rejected."""
        plan = {"steps": []}
        self._write_selected(plan)
        result = self._run_merger()
        self.assertNotEqual(result.returncode, 0)

    # ── Property 3: Step order preserved ───────────────────────────────

    def test_step_order_preserved_in_merged(self):
        """Steps should appear in the same order in merged plan."""
        plan = {"steps": [
            {"task_id": "T3", "action": "create_file", "path": "c.py"},
            {"task_id": "T1", "action": "create_file", "path": "a.py"},
            {"task_id": "T2", "action": "create_file", "path": "b.py"},
        ]}
        self._write_selected(plan)
        self._run_merger()
        merged = self._read_merged()

        task_ids = [s["task_id"] for s in merged["steps"]]
        self.assertEqual(task_ids, ["T3", "T1", "T2"])

    # ── Property 4: Missing required fields → rejection ───────────────

    def test_missing_path_rejected(self):
        """create_file steps without path should be rejected."""
        plan = {"steps": [{"task_id": "T1", "action": "create_file"}]}
        self._write_selected(plan)
        result = self._run_merger()
        self.assertNotEqual(result.returncode, 0)

    def test_missing_action_rejected(self):
        """Steps without action should be rejected."""
        plan = {"steps": [{"task_id": "T1", "path": "out.py"}]}
        self._write_selected(plan)
        result = self._run_merger()
        self.assertNotEqual(result.returncode, 0)

    # ── Property 5: Metadata preserved ────────────────────────────────

    def test_metadata_preserved_in_merged(self):
        """Non-steps metadata should be preserved in merged plan."""
        plan = {
            "steps": [{"task_id": "T1", "action": "create_file", "path": "out.py"}],
            "planner": "test-planner",
            "version": "1.0",
            "custom_field": "preserved",
        }
        self._write_selected(plan)
        self._run_merger()
        merged = self._read_merged()

        self.assertEqual(merged["selected_plan_metadata"]["planner"], "test-planner")
        self.assertEqual(merged["selected_plan_metadata"]["version"], "1.0")
        self.assertEqual(merged["selected_plan_metadata"]["custom_field"], "preserved")

    # ── Property 6: Schema version is set ─────────────────────────────

    def test_merged_plan_has_schema_version(self):
        """Merged plan should have schema_version."""
        plan = {"steps": [{"task_id": "T1", "action": "create_file", "path": "out.py"}]}
        self._write_selected(plan)
        self._run_merger()
        merged = self._read_merged()

        self.assertEqual(merged["schema_version"], "merged_plan_v1")

    # ── Property 7: Source is set ──────────────────────────────────────

    def test_merged_plan_has_source(self):
        """Merged plan should have source field."""
        plan = {"steps": [{"task_id": "T1", "action": "create_file", "path": "out.py"}]}
        self._write_selected(plan)
        self._run_merger()
        merged = self._read_merged()

        self.assertEqual(merged["source"], "selected_plan.json")

    # ── Property 8: Produces artifacts validated ───────────────────────

    def test_produces_artifacts_validated(self):
        """Produces artifacts must have artifact_id and path."""
        plan = {"steps": [{
            "task_id": "T1",
            "action": "create_file",
            "path": "out.py",
            "produces": [{"artifact_id": "A.001", "path": "out.py"}]
        }]}
        self._write_selected(plan)
        self._run_merger()
        merged = self._read_merged()

        self.assertEqual(merged["steps"][0]["produces"][0]["artifact_id"], "A.001")

    def test_produces_missing_artifact_id_rejected(self):
        """Produces without artifact_id should be rejected."""
        plan = {"steps": [{
            "task_id": "T1",
            "action": "create_file",
            "path": "out.py",
            "produces": [{"path": "out.py"}]  # missing artifact_id
        }]}
        self._write_selected(plan)
        result = self._run_merger()
        self.assertNotEqual(result.returncode, 0)


class TestPlanSelectorProperties(unittest.TestCase):
    """Metamorphic properties for the plan selector."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.run_dir = self.tmpdir / ".agentic-runs" / "test_run"
        self.run_dir.mkdir(parents=True)
        self.plans_dir = self.run_dir / "plans"
        self.plans_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_selector(self):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "plan_selector.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir), capture_output=True, text=True,
        )
        return result

    def _read_selected(self):
        return json.loads((self.run_dir / "selected_plan.json").read_text())

    # ── Property: Fewer steps is better ────────────────────────────────

    def test_selector_picks_fewer_steps(self):
        """Selector should pick the plan with fewer steps."""
        plan_many = {"steps": [
            {"task_id": "T1", "action": "create_file"},
            {"task_id": "T2", "action": "create_file"},
            {"task_id": "T3", "action": "create_file"},
        ]}
        plan_few = {"steps": [
            {"task_id": "T1", "action": "create_file"},
        ]}
        (self.plans_dir / "many_plan.json").write_text(json.dumps(plan_many))
        (self.plans_dir / "few_plan.json").write_text(json.dumps(plan_few))

        self._run_selector()
        selected = self._read_selected()

        self.assertEqual(len(selected["steps"]), 1)

    # ── Property: Empty plans rejected ─────────────────────────────────

    def test_empty_plans_rejected(self):
        """Selector should reject plans with no steps."""
        plan = {"steps": []}
        (self.plans_dir / "empty_plan.json").write_text(json.dumps(plan))

        result = self._run_selector()
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
