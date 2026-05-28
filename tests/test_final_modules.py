"""Tests for the final 6 untested modules.

These are the last modules without test references. The health check
flagged them as the final gaps.

Modules covered:
  runtime/harness_health.py
  runtime/plan_graph_v1_builder.py
  runtime/run_prompt_compiler_eval.py
  diagnostics/meta_harness/run_meta_harness.py
  evaluation/stage1_multiframe/run_mercury_live_capture.py
  fixtures/golden_strict_p2_minimal/materialize.py
"""
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTIC_PI = ROOT / ".agentic-pi"


class TestHarnessHealth(unittest.TestCase):
    """Tests for runtime/harness_health.py."""

    def test_harness_health_runs(self):
        """harness_health.py runs without error."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(AGENTIC_PI / "runtime" / "harness_health.py"), "--json"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertIn("module_coverage", data)
        self.assertIn("critical_path", data)
        self.assertIn("dead_code", data)
        self.assertIn("gate_coverage", data)

    def test_critical_only_flag(self):
        """--critical-only flag works."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(AGENTIC_PI / "runtime" / "harness_health.py"), "--critical-only"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CRITICAL PATH GAPS", result.stdout)

    def test_json_output_is_valid(self):
        """--json output is valid JSON."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(AGENTIC_PI / "runtime" / "harness_health.py"), "--json"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        data = json.loads(result.stdout)
        self.assertIsInstance(data["module_coverage"]["uncovered_list"], list)
        self.assertIsInstance(data["critical_path"]["gap_list"], list)


class TestPlanGraphV1Builder(unittest.TestCase):
    """Tests for runtime/plan_graph_v1_builder.py."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "plan_graph_v1_builder",
            AGENTIC_PI / "runtime" / "plan_graph_v1_builder.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_loads_graph_from_fixture(self):
        """PlanGraphV1Builder loads nodes and edges from fixture."""
        mod = self._load()
        fixture = {
            "nodes": [{"id": "N1", "type": "task"}, {"id": "N2", "type": "task"}],
            "edges": [{"source": "N1", "target": "N2"}],
        }
        path = self.tmpdir / "graph.json"
        path.write_text(json.dumps(fixture))
        builder = mod.PlanGraphV1Builder(str(path))
        self.assertEqual(len(builder.graph["nodes"]), 2)
        self.assertEqual(len(builder.graph["edges"]), 1)

    def test_get_node_by_id(self):
        """get_node returns the node with matching id."""
        mod = self._load()
        fixture = {"nodes": [{"id": "N1", "type": "task"}], "edges": []}
        path = self.tmpdir / "graph.json"
        path.write_text(json.dumps(fixture))
        builder = mod.PlanGraphV1Builder(str(path))
        node = builder.get_node("N1")
        self.assertIsNotNone(node)
        self.assertEqual(node["id"], "N1")

    def test_get_node_returns_none_for_missing(self):
        """get_node returns None for missing id."""
        mod = self._load()
        fixture = {"nodes": [], "edges": []}
        path = self.tmpdir / "graph.json"
        path.write_text(json.dumps(fixture))
        builder = mod.PlanGraphV1Builder(str(path))
        self.assertIsNone(builder.get_node("MISSING"))

    def test_fails_on_missing_fixture(self):
        """Raises FileNotFoundError when fixture missing."""
        mod = self._load()
        with self.assertRaises(FileNotFoundError):
            mod.PlanGraphV1Builder(str(self.tmpdir / "nonexistent.json"))


class TestRunPromptCompilerEval(unittest.TestCase):
    """Tests for runtime/run_prompt_compiler_eval.py."""

    def test_loads_without_error(self):
        """Module can be imported."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_prompt_compiler_eval",
            AGENTIC_PI / "runtime" / "run_prompt_compiler_eval.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, "main") or hasattr(mod, "run_eval"))


class TestRunMetaHarness(unittest.TestCase):
    """Tests for diagnostics/meta_harness/run_meta_harness.py."""

    def test_loads_without_error(self):
        """Module can be imported."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_meta_harness",
            AGENTIC_PI / "diagnostics" / "meta_harness" / "run_meta_harness.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, "run_case") or hasattr(mod, "main"))

    def test_manifest_exists(self):
        """Meta-harness manifest.json exists."""
        manifest = AGENTIC_PI / "diagnostics" / "meta_harness" / "manifest.json"
        self.assertTrue(manifest.exists(), f"manifest.json not found at {manifest}")


class TestRunMercuryLiveCapture(unittest.TestCase):
    """Tests for evaluation/stage1_multiframe/run_mercury_live_capture.py."""

    def test_loads_without_error(self):
        """Module can be imported."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_mercury_live_capture",
            AGENTIC_PI / "evaluation" / "stage1_multiframe" / "run_mercury_live_capture.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, "main") or callable(mod))


class TestMaterialize(unittest.TestCase):
    """Tests for fixtures/golden_strict_p2_minimal/materialize.py."""

    def test_materialize_runs(self):
        """materialize.py runs and creates the fixture."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(AGENTIC_PI / "fixtures" / "golden_strict_p2_minimal" / "materialize.py")],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        # Verify the fixture was created
        fixture_dir = ROOT / ".agentic-runs" / "golden_strict_p2_minimal"
        self.assertTrue(fixture_dir.exists())
        self.assertTrue((fixture_dir / "goal_contract.json").exists())


if __name__ == "__main__":
    unittest.main()
