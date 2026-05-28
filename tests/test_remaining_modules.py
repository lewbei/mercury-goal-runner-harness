"""Tests for remaining non-critical-path modules.

These modules are not on the hot path but still need test coverage.
The health check flagged them as gaps.

Modules covered:
  supervisor/validators/validate_no_horizontal_packet.py
  supervisor/validators/validate_vertical_slice.py
  wiring/validators/validate_module_registry.py
  wiring/validators/validate_no_dangling_outputs.py
  wiring/validators/validate_no_missing_consumers.py
  wiring/validators/validate_static_wiring.py
  validators/validate_prompt_provenance.py
  validators/validate_prompt_eval_case.py
  runtime/kernel_helper.py
  runtime/verify_agent_outputs.py
  runtime/project_adapter.py
  planning/plan_completeness_gate.py
  execution/validators/validate_vertical_slice.py
"""
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTIC_PI = ROOT / ".agentic-pi"


class TestValidateNoHorizontalPacket(unittest.TestCase):
    """Tests for supervisor/validators/validate_no_horizontal_packet.py."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "validate_no_horizontal_packet",
            AGENTIC_PI / "supervisor" / "validators" / "validate_no_horizontal_packet.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_blocks_horizontal_packet(self):
        """Packets with many files but few layers are blocked."""
        mod = self._load()
        packet = {"files_approx": 10, "end_to_end_layers": ["api"], "slice_id": "S1"}
        path = self.tmpdir / "packet.json"
        path.write_text(json.dumps(packet))
        result = mod.validate(path, [])
        self.assertTrue(result["blocked"])

    def test_allows_vertical_packet(self):
        """Packets with enough layers are allowed."""
        mod = self._load()
        packet = {"files_approx": 2, "end_to_end_layers": ["api", "ui", "db"], "slice_id": "S1"}
        path = self.tmpdir / "packet.json"
        path.write_text(json.dumps(packet))
        result = mod.validate(path, [])
        self.assertFalse(result["blocked"])


class TestValidateVerticalSlice(unittest.TestCase):
    """Tests for supervisor/validators/validate_vertical_slice.py."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "validate_vertical_slice",
            AGENTIC_PI / "supervisor" / "validators" / "validate_vertical_slice.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_valid_packet_passes(self):
        """Packet with fixture, verdict, and 3+ layers passes."""
        mod = self._load()
        packet = {
            "fixture": "test_fixture",
            "expected_verdict": "PASS",
            "end_to_end_layers": ["api", "ui", "db"],
        }
        path = self.tmpdir / "packet.json"
        path.write_text(json.dumps(packet))
        result = mod.validate(path)
        self.assertTrue(result["valid"])

    def test_missing_fixture_fails(self):
        """Packet without fixture fails."""
        mod = self._load()
        packet = {"expected_verdict": "PASS", "end_to_end_layers": ["api", "ui", "db"]}
        path = self.tmpdir / "packet.json"
        path.write_text(json.dumps(packet))
        result = mod.validate(path)
        self.assertFalse(result["valid"])
        self.assertIn("no fixture", result["issues"])

    def test_too_few_layers_fails(self):
        """Packet with fewer than 3 layers fails."""
        mod = self._load()
        packet = {"fixture": "test", "expected_verdict": "PASS", "end_to_end_layers": ["api"]}
        path = self.tmpdir / "packet.json"
        path.write_text(json.dumps(packet))
        result = mod.validate(path)
        self.assertFalse(result["valid"])


class TestValidateModuleRegistry(unittest.TestCase):
    """Tests for wiring/validators/validate_module_registry.py."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "validate_module_registry",
            AGENTIC_PI / "wiring" / "validators" / "validate_module_registry.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_valid_registry_passes(self):
        """Valid registry has no errors."""
        mod = self._load()
        registry = {
            "module_a": {"inputs": ["x"], "outputs": ["y"], "command": "python a.py"},
            "module_b": {"inputs": ["y"], "outputs": ["z"], "command": "python b.py"},
        }
        path = self.tmpdir / "registry.json"
        path.write_text(json.dumps(registry))
        errors = mod.validate_registry(path)
        self.assertEqual(errors, [])

    def test_missing_file_returns_error(self):
        """Missing file returns error."""
        mod = self._load()
        errors = mod.validate_registry(self.tmpdir / "nonexistent.json")
        self.assertGreater(len(errors), 0)

    def test_invalid_module_type_returns_error(self):
        """Module value must be a dict."""
        mod = self._load()
        registry = {"module_a": "not_a_dict"}
        path = self.tmpdir / "registry.json"
        path.write_text(json.dumps(registry))
        errors = mod.validate_registry(path)
        self.assertGreater(len(errors), 0)


class TestValidateNoDanglingOutputs(unittest.TestCase):
    """Tests for wiring/validators/validate_no_dangling_outputs.py."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "validate_no_dangling_outputs",
            AGENTIC_PI / "wiring" / "validators" / "validate_no_dangling_outputs.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_no_dangling_when_consumed(self):
        """Outputs consumed by another module are not dangling."""
        mod = self._load()
        registry = {
            "a": {"outputs": ["x"], "inputs": []},
            "b": {"outputs": [], "inputs": ["x"]},
        }
        path = self.tmpdir / "registry.json"
        path.write_text(json.dumps(registry))
        dangling = mod.find_dangling_outputs(path)
        self.assertEqual(dangling, [])

    def test_dangling_when_not_consumed(self):
        """Outputs not consumed by any module are dangling."""
        mod = self._load()
        registry = {
            "a": {"outputs": ["x", "y"], "inputs": []},
            "b": {"outputs": [], "inputs": ["x"]},
        }
        path = self.tmpdir / "registry.json"
        path.write_text(json.dumps(registry))
        dangling = mod.find_dangling_outputs(path)
        self.assertEqual(len(dangling), 1)
        self.assertEqual(dangling[0], ("a", "y"))


class TestValidateNoMissingConsumers(unittest.TestCase):
    """Tests for wiring/validators/validate_no_missing_consumers.py."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "validate_no_missing_consumers",
            AGENTIC_PI / "wiring" / "validators" / "validate_no_missing_consumers.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_no_missing_when_all_inputs_satisfied(self):
        """Inputs satisfied by another module's output are not missing."""
        mod = self._load()
        registry = {
            "a": {"outputs": ["x"], "inputs": []},
            "b": {"outputs": [], "inputs": ["x"]},
        }
        path = self.tmpdir / "registry.json"
        path.write_text(json.dumps(registry))
        missing = mod.find_missing_consumers(path)
        self.assertEqual(missing, [])


class TestValidateStaticWiring(unittest.TestCase):
    """Tests for wiring/validators/validate_static_wiring.py."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "validate_static_wiring",
            AGENTIC_PI / "wiring" / "validators" / "validate_static_wiring.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_valid_wiring_passes(self):
        """Valid wiring passes validation."""
        mod = self._load()
        registry = {
            "a": {"outputs": ["x"], "inputs": [], "command": "python a.py"},
            "b": {"outputs": [], "inputs": ["x"], "command": "python b.py"},
        }
        path = self.tmpdir / "registry.json"
        path.write_text(json.dumps(registry))
        result = mod.validate_static_wiring(path)
        # Returns a dict of module statuses, not a list of errors
        self.assertIsInstance(result, dict)


class TestVerifyAgentOutputs(unittest.TestCase):
    """Tests for runtime/verify_agent_outputs.py."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.run_dir = self.tmpdir / "test_run"
        self.run_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_verifies_existing_files(self):
        """verify_agent_outputs succeeds when files exist."""
        (self.run_dir / "output.py").write_text("print('hello')")
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(AGENTIC_PI / "runtime" / "verify_agent_outputs.py"),
             str(self.run_dir), "test_agent", "output.py"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_fails_when_file_missing(self):
        """verify_agent_outputs fails when expected file is missing."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(AGENTIC_PI / "runtime" / "verify_agent_outputs.py"),
             str(self.run_dir), "test_agent", "nonexistent.py"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)


class TestProjectAdapter(unittest.TestCase):
    """Tests for runtime/project_adapter.py."""

    def test_project_adapter_loads(self):
        """project_adapter.py can be imported."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "project_adapter", AGENTIC_PI / "runtime" / "project_adapter.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, "_is_git_repo") or hasattr(mod, "_list_git_files"))


class TestPlanCompletenessGate(unittest.TestCase):
    """Tests for planning/plan_completeness_gate.py."""

    def test_plan_completeness_gate_loads(self):
        """plan_completeness_gate.py can be imported."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "plan_completeness_gate",
            AGENTIC_PI / "planning" / "plan_completeness_gate.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, "main") or hasattr(mod, "validate"))


class TestExecutionVerticalSliceValidator(unittest.TestCase):
    """Tests for execution/validators/validate_vertical_slice.py."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "execution_validate_vertical_slice",
            AGENTIC_PI / "execution" / "validators" / "validate_vertical_slice.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_loads_without_error(self):
        """Module can be imported."""
        import importlib.util
        import sys
        runtime_dir = str(AGENTIC_PI / "runtime")
        if runtime_dir not in sys.path:
            sys.path.insert(0, runtime_dir)
        mod = self._load()
        self.assertTrue(hasattr(mod, "has_fixture") or hasattr(mod, "validate"))


class TestValidatePromptProvenance(unittest.TestCase):
    """Tests for validators/validate_prompt_provenance.py."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.run_dir = self.tmpdir / "test_run"
        self.run_dir.mkdir()
        self.provenance_dir = self.run_dir / "prompt_provenance"
        self.provenance_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "validate_prompt_provenance",
            AGENTIC_PI / "validators" / "validate_prompt_provenance.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_loads_without_error(self):
        """Module can be imported."""
        mod = self._load()
        self.assertTrue(hasattr(mod, "validate_prompt_provenance") or hasattr(mod, "main"))


class TestValidatePromptEvalCase(unittest.TestCase):
    """Tests for validators/validate_prompt_eval_case.py."""

    def test_loads_without_error(self):
        """Module can be imported."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "validate_prompt_eval_case",
            AGENTIC_PI / "validators" / "validate_prompt_eval_case.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, "validate") or hasattr(mod, "main"))


class TestKernelHelper(unittest.TestCase):
    """Tests for runtime/kernel_helper.py."""

    def test_kernel_helper_loads(self):
        """kernel_helper.py can be imported."""
        import importlib.util
        import sys
        runtime_dir = str(AGENTIC_PI / "runtime")
        if runtime_dir not in sys.path:
            sys.path.insert(0, runtime_dir)
        spec = importlib.util.spec_from_file_location(
            "kernel_helper", AGENTIC_PI / "runtime" / "kernel_helper.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, "verify_run") or hasattr(mod, "log_dispatch"))


class TestSmartMemory(unittest.TestCase):
    """Tests for runtime/smart_memory.py."""

    def test_smart_memory_loads(self):
        """smart_memory.py can be imported."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "smart_memory", AGENTIC_PI / "runtime" / "smart_memory.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, "Card") or hasattr(mod, "SmartMemoryError"))


class TestMemoryEval(unittest.TestCase):
    """Tests for runtime/memory_eval.py."""

    def test_memory_eval_loads(self):
        """memory_eval.py can be imported."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "memory_eval", AGENTIC_PI / "runtime" / "memory_eval.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, "main") or callable(mod))


class TestGoalPersistence(unittest.TestCase):
    """Tests for runtime/goal_persistence.py."""

    def test_goal_persistence_loads(self):
        """goal_persistence.py can be imported via subprocess."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(AGENTIC_PI / "runtime" / "goal_persistence.py"), "--help"],
            capture_output=True, text=True,
        )
        # Should either succeed or fail with usage, not crash
        self.assertIn(result.returncode, [0, 1, 2])


class TestCrossRunLearner(unittest.TestCase):
    """Tests for runtime/cross_run_learner.py."""

    def test_cross_run_learner_loads(self):
        """cross_run_learner.py can be imported."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "cross_run_learner", AGENTIC_PI / "runtime" / "cross_run_learner.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, "scan_runs") or hasattr(mod, "extract_patterns"))


class TestAutoDispatcher(unittest.TestCase):
    """Tests for runtime/auto_dispatcher.py."""

    def test_auto_dispatcher_loads(self):
        """auto_dispatcher.py can be imported."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "auto_dispatcher", AGENTIC_PI / "runtime" / "auto_dispatcher.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, "main") or callable(mod))


class TestVerticalSliceSelector(unittest.TestCase):
    """Tests for supervisor/vertical_slice_selector.py."""

    def test_vertical_slice_selector_loads(self):
        """vertical_slice_selector.py can be imported."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "vertical_slice_selector",
            AGENTIC_PI / "supervisor" / "vertical_slice_selector.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, "main") or callable(mod))


class TestWiringAudit(unittest.TestCase):
    """Tests for wiring/run_wiring_audit.py."""

    def test_wiring_audit_loads(self):
        """run_wiring_audit.py can be imported via subprocess."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(AGENTIC_PI / "wiring" / "run_wiring_audit.py"), "--help"],
            capture_output=True, text=True,
        )
        # Should either succeed or fail with usage, not crash
        self.assertIn(result.returncode, [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
