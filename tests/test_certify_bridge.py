"""Tests for .agentic-pi/runtime/certify_bridge.py.

Covers:
- normalize_for_certifier: trace.jsonl creation, step log normalization
- ensure_plan_artifacts: plan_graph/merged_plan/selected_plan creation
- ensure_verifier_contract: verifier_contract.json creation
- _normalize_verifier_artifacts: unknown field stripping
- certify: full pipeline integration
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".agentic-pi" / "runtime"
BRIDGE_PATH = RUNTIME / "certify_bridge.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("certify_bridge", BRIDGE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestNormalizeForCertifier(unittest.TestCase):
    """Test normalize_for_certifier."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.run_id = "test_run"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_trace_jsonl_if_missing(self):
        """normalize_for_certifier creates trace.jsonl if it doesn't exist."""
        self.mod.normalize_for_certifier(self.tmpdir, self.run_id)
        trace_path = self.tmpdir / "trace.jsonl"
        self.assertTrue(trace_path.exists())
        data = json.loads(trace_path.read_text())
        self.assertIn("timestamp", data)
        self.assertEqual(data["event"], "run_completed")

    def test_creates_step_logs_dir_if_missing(self):
        """normalize_for_certifier creates step_logs/ if it doesn't exist."""
        self.mod.normalize_for_certifier(self.tmpdir, self.run_id)
        self.assertTrue((self.tmpdir / "step_logs").is_dir())

    def test_normalizes_step_log_run_id(self):
        """Step logs with wrong run_id get corrected."""
        step_dir = self.tmpdir / "step_logs"
        step_dir.mkdir()
        step = {"run_id": "wrong_id", "step_id": 1, "status": "PASSED",
                "action_taken": "create_file", "files_touched": ["out.py"],
                "commands_run": [], "evidence": ["done"],
                "pass_condition_satisfied": True, "remaining_work": []}
        (step_dir / "001.json").write_text(json.dumps(step))

        self.mod.normalize_for_certifier(self.tmpdir, self.run_id)
        result = json.loads((step_dir / "001.json").read_text())
        self.assertEqual(result["run_id"], self.run_id)

    def test_normalizes_string_evidence_to_list(self):
        """String evidence gets wrapped in a list."""
        step_dir = self.tmpdir / "step_logs"
        step_dir.mkdir()
        step = {"run_id": self.run_id, "step_id": 1, "status": "PASSED",
                "action_taken": "create_file", "files_touched": ["out.py"],
                "commands_run": [], "evidence": "single evidence",
                "pass_condition_satisfied": True, "remaining_work": []}
        (step_dir / "001.json").write_text(json.dumps(step))

        self.mod.normalize_for_certifier(self.tmpdir, self.run_id)
        result = json.loads((step_dir / "001.json").read_text())
        self.assertIsInstance(result["evidence"], list)
        self.assertEqual(result["evidence"], ["single evidence"])

    def test_normalizes_string_files_touched_to_list(self):
        """String files_touched gets wrapped in a list."""
        step_dir = self.tmpdir / "step_logs"
        step_dir.mkdir()
        step = {"run_id": self.run_id, "step_id": 1, "status": "PASSED",
                "action_taken": "create_file", "files_touched": "out.py",
                "commands_run": [], "evidence": ["done"],
                "pass_condition_satisfied": True, "remaining_work": []}
        (step_dir / "001.json").write_text(json.dumps(step))

        self.mod.normalize_for_certifier(self.tmpdir, self.run_id)
        result = json.loads((step_dir / "001.json").read_text())
        self.assertIsInstance(result["files_touched"], list)

    def test_normalizes_empty_remaining_work(self):
        """Non-empty remaining_work gets cleared."""
        step_dir = self.tmpdir / "step_logs"
        step_dir.mkdir()
        step = {"run_id": self.run_id, "step_id": 1, "status": "PASSED",
                "action_taken": "create_file", "files_touched": ["out.py"],
                "commands_run": [], "evidence": ["done"],
                "pass_condition_satisfied": True, "remaining_work": ["more work"]}
        (step_dir / "001.json").write_text(json.dumps(step))

        self.mod.normalize_for_certifier(self.tmpdir, self.run_id)
        result = json.loads((step_dir / "001.json").read_text())
        self.assertEqual(result["remaining_work"], [])


class TestEnsurePlanArtifacts(unittest.TestCase):
    """Test ensure_plan_artifacts."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.run_id = "test_run"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_plan_graph_from_step_logs(self):
        """Creates plan_graph.json from step logs."""
        step_dir = self.tmpdir / "step_logs"
        step_dir.mkdir()
        step = {"step_id": 1, "action_taken": "create_file",
                "files_touched": ["output.py"]}
        (step_dir / "001.json").write_text(json.dumps(step))

        self.mod.ensure_plan_artifacts(self.tmpdir, self.run_id)
        pg = json.loads((self.tmpdir / "plan_graph.json").read_text())
        self.assertIn("nodes", pg)
        self.assertIn("edges", pg)
        self.assertEqual(len(pg["nodes"]), 1)

    def test_creates_merged_plan_from_step_logs(self):
        """Creates merged_plan.json from step logs."""
        step_dir = self.tmpdir / "step_logs"
        step_dir.mkdir()
        step = {"step_id": 1, "action_taken": "create_file",
                "files_touched": ["output.py"]}
        (step_dir / "001.json").write_text(json.dumps(step))

        self.mod.ensure_plan_artifacts(self.tmpdir, self.run_id)
        mp = json.loads((self.tmpdir / "merged_plan.json").read_text())
        self.assertIn("steps", mp)
        self.assertEqual(len(mp["steps"]), 1)

    def test_creates_selected_plan_if_missing(self):
        """Creates selected_plan.json if missing."""
        self.mod.ensure_plan_artifacts(self.tmpdir, self.run_id)
        sp = json.loads((self.tmpdir / "selected_plan.json").read_text())
        self.assertIn("selected", sp)

    def test_creates_default_artifacts_when_no_step_logs(self):
        """Creates default artifacts when step_logs is empty."""
        self.mod.ensure_plan_artifacts(self.tmpdir, self.run_id)
        pg = json.loads((self.tmpdir / "plan_graph.json").read_text())
        mp = json.loads((self.tmpdir / "merged_plan.json").read_text())
        self.assertIn("nodes", pg)
        self.assertIn("steps", mp)

    def test_does_not_overwrite_existing_selected_plan(self):
        """Does not overwrite existing selected_plan.json."""
        sp = self.tmpdir / "selected_plan.json"
        sp.write_text(json.dumps({"selected": "custom_planner"}))
        self.mod.ensure_plan_artifacts(self.tmpdir, self.run_id)
        result = json.loads(sp.read_text())
        self.assertEqual(result["selected"], "custom_planner")

    def test_multiple_steps_produce_edges(self):
        """Multiple steps produce dependency edges."""
        step_dir = self.tmpdir / "step_logs"
        step_dir.mkdir()
        for i in range(1, 4):
            step = {"step_id": i, "action_taken": "create_file",
                    "files_touched": [f"out_{i}.py"]}
            (step_dir / f"{i:03d}.json").write_text(json.dumps(step))

        self.mod.ensure_plan_artifacts(self.tmpdir, self.run_id)
        pg = json.loads((self.tmpdir / "plan_graph.json").read_text())
        self.assertEqual(len(pg["nodes"]), 3)
        self.assertEqual(len(pg["edges"]), 2)  # T1->T2, T2->T3


class TestEnsureVerifierContract(unittest.TestCase):
    """Test ensure_verifier_contract."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.run_id = "test_run"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_verifier_contract(self):
        """Creates verifier_contract.json."""
        self.mod.ensure_verifier_contract(self.tmpdir, self.run_id)
        vc = json.loads((self.tmpdir / "verifier_contract.json").read_text())
        self.assertEqual(vc["run_id"], self.run_id)
        self.assertEqual(vc["required_verifier_level"], "P2")

    def test_uses_goal_contract_outputs_as_targets(self):
        """Uses final_outputs from goal_contract.json as targets."""
        gc = {"final_outputs": ["main.py", "utils.py"]}
        (self.tmpdir / "goal_contract.json").write_text(json.dumps(gc))

        self.mod.ensure_verifier_contract(self.tmpdir, self.run_id)
        vc = json.loads((self.tmpdir / "verifier_contract.json").read_text())
        self.assertEqual(vc["target_artifacts"], ["main.py", "utils.py"])

    def test_defaults_to_output_py_when_no_goal_contract(self):
        """Defaults to output.py when no goal_contract.json exists."""
        self.mod.ensure_verifier_contract(self.tmpdir, self.run_id)
        vc = json.loads((self.tmpdir / "verifier_contract.json").read_text())
        self.assertEqual(vc["target_artifacts"], ["output.py"])

    def test_does_not_overwrite_existing(self):
        """Does not overwrite existing verifier_contract.json."""
        vc_path = self.tmpdir / "verifier_contract.json"
        vc_path.write_text(json.dumps({"custom": True}))
        self.mod.ensure_verifier_contract(self.tmpdir, self.run_id)
        result = json.loads(vc_path.read_text())
        self.assertTrue(result["custom"])


class TestNormalizeVerifierArtifacts(unittest.TestCase):
    """Test _normalize_verifier_artifacts."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_strips_unknown_fields_when_schema_exists(self):
        """Strips fields not in schema."""
        schema_dir = ROOT / ".agentic-pi" / "schemas"
        schema_path = schema_dir / "verifier_artifact.schema.json"
        if not schema_path.exists():
            self.skipTest("Schema file not found")

        va_dir = self.tmpdir / "verifier_artifacts"
        va_dir.mkdir()
        artifact = {
            "artifact_id": "V.TEST",
            "run_id": "test",
            "kind": "test",
            "verdict": "PASS",
            "unknown_field": "should be stripped",
            "another_unknown": 42,
        }
        (va_dir / "V_TEST.json").write_text(json.dumps(artifact))

        self.mod._normalize_verifier_artifacts(self.tmpdir)
        result = json.loads((va_dir / "V_TEST.json").read_text())
        self.assertNotIn("unknown_field", result)
        self.assertNotIn("another_unknown", result)
        self.assertIn("artifact_id", result)

    def test_noop_when_no_schema(self):
        """Does nothing when schema file doesn't exist."""
        va_dir = self.tmpdir / "verifier_artifacts"
        va_dir.mkdir()
        artifact = {"artifact_id": "V.TEST", "unknown": True}
        (va_dir / "V_TEST.json").write_text(json.dumps(artifact))

        # Mock ROOT to point to a non-existent schemas directory
        with patch.object(self.mod, "ROOT", self.tmpdir):
            self.mod._normalize_verifier_artifacts(self.tmpdir)
        result = json.loads((va_dir / "V_TEST.json").read_text())
        self.assertTrue(result["unknown"])  # Not stripped

    def test_noop_when_no_verifier_artifacts_dir(self):
        """Does nothing when verifier_artifacts/ doesn't exist."""
        # Should not raise
        self.mod._normalize_verifier_artifacts(self.tmpdir)


class TestCertify(unittest.TestCase):
    """Test certify function."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_returns_done_fail_when_no_certification(self):
        """Returns DONE_FAIL when certification.json doesn't exist."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            result = self.mod.certify(self.tmpdir)
            self.assertEqual(result, "DONE_FAIL")

    def test_returns_status_from_certification(self):
        """Returns status from certification.json."""
        cert = {"status": "CERTIFIED_DONE"}
        (self.tmpdir / "certification.json").write_text(json.dumps(cert))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            result = self.mod.certify(self.tmpdir)
            self.assertEqual(result, "CERTIFIED_DONE")

    def test_calls_normalize_for_certifier(self):
        """certify calls normalize_for_certifier."""
        with patch.object(self.mod, "normalize_for_certifier") as mock_norm:
            with patch.object(self.mod, "ensure_plan_artifacts"):
                with patch.object(self.mod, "ensure_verifier_contract"):
                    with patch.object(self.mod, "_normalize_verifier_artifacts"):
                        with patch("subprocess.run"):
                            self.mod.certify(self.tmpdir)
                            mock_norm.assert_called_once()

    def test_calls_ensure_plan_artifacts(self):
        """certify calls ensure_plan_artifacts."""
        with patch.object(self.mod, "normalize_for_certifier"):
            with patch.object(self.mod, "ensure_plan_artifacts") as mock_plan:
                with patch.object(self.mod, "ensure_verifier_contract"):
                    with patch.object(self.mod, "_normalize_verifier_artifacts"):
                        with patch("subprocess.run"):
                            self.mod.certify(self.tmpdir)
                            mock_plan.assert_called_once()

    def test_calls_ensure_verifier_contract(self):
        """certify calls ensure_verifier_contract."""
        with patch.object(self.mod, "normalize_for_certifier"):
            with patch.object(self.mod, "ensure_plan_artifacts"):
                with patch.object(self.mod, "ensure_verifier_contract") as mock_vc:
                    with patch.object(self.mod, "_normalize_verifier_artifacts"):
                        with patch("subprocess.run"):
                            self.mod.certify(self.tmpdir)
                            mock_vc.assert_called_once()


if __name__ == "__main__":
    unittest.main()
