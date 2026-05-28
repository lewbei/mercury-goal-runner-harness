"""Tests for remaining critical path modules.

These modules are on the hot path (called by run_goal.py or certify_run.py)
but had zero test coverage. The health check flagged them as gaps.

Modules covered:
  prompt_provenance.py    — prompt lineage tracking
  trace_logger.py         — trace event logging
  context_builder.py      — context packet for guarded worker
  build_repair_prompt.py  — repair prompt with memory context
  run_subagent_memory.py  — subagent learning capture
  update_memory_from_runs.py — memory validation
  check_matrix.py         — horizontal check matrix
  adversarial_loop.py     — diagnostic repair loop
  context_engineer.py     — context engineering
  context_injector.py     — skill context injection
"""
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".agentic-pi" / "runtime"


class TestPromptProvenance(unittest.TestCase):
    """Tests for prompt_provenance.py."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.run_dir = self.tmpdir / "test_run"
        self.run_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_contract(self, contract):
        (self.run_dir / "goal_contract.json").write_text(json.dumps(contract))

    def test_build_provenance_from_contract(self):
        """build_prompt_provenance extracts prompt info from contract."""
        contract = {
            "run_id": "test_run",
            "raw_user_prompt": "Create a README",
            "execution_prompt": "Create a README explaining the harness",
        }
        self._write_contract(contract)

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "prompt_provenance", RUNTIME / "prompt_provenance.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        result = mod.build_prompt_provenance(self.run_dir)
        self.assertEqual(result["run_id"], "test_run")
        self.assertEqual(result["raw_prompt"]["text"], "Create a README")
        self.assertEqual(result["execution_prompt"]["text"], "Create a README explaining the harness")
        self.assertFalse(result["authority"]["can_certify_done"])

    def test_provenance_hashes_are_stable(self):
        """SHA256 hashes are deterministic."""
        contract = {
            "run_id": "test_run",
            "raw_user_prompt": "test prompt",
            "execution_prompt": "test execution",
        }
        self._write_contract(contract)

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "prompt_provenance", RUNTIME / "prompt_provenance.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        result = mod.build_prompt_provenance(self.run_dir)
        self.assertEqual(
            result["raw_prompt"]["sha256"],
            mod.sha256_text("test prompt"),
        )

    def test_fails_without_goal_contract(self):
        """Raises FileNotFoundError when goal_contract.json missing."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "prompt_provenance", RUNTIME / "prompt_provenance.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        with self.assertRaises(FileNotFoundError):
            mod.build_prompt_provenance(self.run_dir)

    def test_record_provenance_writes_file(self):
        """record_prompt_provenance writes the artifact file."""
        contract = {
            "run_id": "test_run",
            "raw_user_prompt": "test",
            "execution_prompt": "test exec",
        }
        self._write_contract(contract)

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "prompt_provenance", RUNTIME / "prompt_provenance.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        out_path = mod.record_prompt_provenance(self.run_dir)
        self.assertTrue(out_path.exists())
        data = json.loads(out_path.read_text())
        self.assertEqual(data["schema_version"], "prompt_provenance_v1")


class TestTraceLogger(unittest.TestCase):
    """Tests for trace_logger.py."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_writes_trace_event(self):
        """trace_logger appends JSONL event to trace.jsonl."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "trace_logger.py"),
             str(self.tmpdir), "--agent", "test", "--event", "run_started"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        trace_path = self.tmpdir / "trace.jsonl"
        self.assertTrue(trace_path.exists())
        event = json.loads(trace_path.read_text().strip())
        self.assertEqual(event["agent"], "test")
        self.assertEqual(event["event"], "run_started")

    def test_appends_multiple_events(self):
        """trace_logger appends (doesn't overwrite) events."""
        import subprocess, sys
        for i in range(3):
            subprocess.run(
                [sys.executable, str(RUNTIME / "trace_logger.py"),
                 str(self.tmpdir), "--agent", "test", "--event", f"event_{i}"],
                capture_output=True, text=True,
            )
        lines = (self.tmpdir / "trace.jsonl").read_text().strip().split("\n")
        self.assertEqual(len(lines), 3)

    def test_includes_data_hash(self):
        """trace_logger includes data_hash for data integrity."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "trace_logger.py"),
             str(self.tmpdir), "--agent", "test", "--event", "test",
             "--data", '{"key": "value"}'],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        event = json.loads((self.tmpdir / "trace.jsonl").read_text().strip())
        self.assertIn("data_hash", event)
        self.assertIsNotNone(event["data_hash"])


class TestContextBuilder(unittest.TestCase):
    """Tests for context_builder.py."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.run_dir = self.tmpdir / ".agentic-runs" / "test_run"
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_builds_context_from_contract(self):
        """context_builder creates context.json from goal contract."""
        contract = {
            "run_id": "test_run",
            "done_criteria": ["output.py exists"],
            "final_outputs": ["output.py"],
        }
        (self.run_dir / "goal_contract.json").write_text(json.dumps(contract))

        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "context_builder.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir), capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        context_path = self.run_dir / "context.json"
        self.assertTrue(context_path.exists())
        context = json.loads(context_path.read_text())
        self.assertEqual(context["run_id"], "test_run")
        self.assertIn("allowed_tools", context)
        self.assertIn("forbidden_paths", context)

    def test_includes_recent_steps(self):
        """context_builder includes last two step logs."""
        contract = {"run_id": "test_run", "done_criteria": []}
        (self.run_dir / "goal_contract.json").write_text(json.dumps(contract))

        step_dir = self.run_dir / "step_logs"
        step_dir.mkdir()
        for i in range(5):
            (step_dir / f"{i:03d}.json").write_text(json.dumps({"step_id": i}))

        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "context_builder.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir), capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        context = json.loads((self.run_dir / "context.json").read_text())
        self.assertEqual(len(context["recent_steps"]), 2)

    def test_fails_without_contract(self):
        """context_builder fails when goal_contract.json missing."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "context_builder.py"), "--run-id", "test_run"],
            cwd=str(self.tmpdir), capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)


class TestBuildRepairPrompt(unittest.TestCase):
    """Tests for build_repair_prompt.py."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.run_dir = self.tmpdir / "test_run"
        self.run_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_extract_errors_from_certification(self):
        """extract_errors reads failures from certification.json."""
        cert = {"failed_checks": ["check 1 failed", "check 2 failed"]}
        (self.run_dir / "certification.json").write_text(json.dumps(cert))

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_repair_prompt", RUNTIME / "build_repair_prompt.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        errors = mod.extract_errors(self.run_dir)
        self.assertEqual(len(errors), 2)
        self.assertIn("check 1 failed", errors)

    def test_extract_errors_returns_default_when_missing(self):
        """extract_errors returns default message when certification.json missing."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_repair_prompt", RUNTIME / "build_repair_prompt.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        errors = mod.extract_errors(self.run_dir)
        self.assertEqual(len(errors), 1)
        self.assertIn("not found", errors[0])


class TestRunSubagentMemory(unittest.TestCase):
    """Tests for run_subagent_memory.py."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.run_dir = self.tmpdir / "test_run"
        self.run_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_gather_context_from_step_logs(self):
        """gather_context reads step logs and thinking plan."""
        (self.run_dir / "thinking_plan.md").write_text("# Plan\nDo stuff")
        step_dir = self.run_dir / "step_logs"
        step_dir.mkdir()
        (step_dir / "001.json").write_text(json.dumps({
            "step_id": 1, "status": "PASSED", "action_taken": "create_file",
            "files_touched": ["out.py"], "evidence": ["done"],
        }))

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_subagent_memory", RUNTIME / "run_subagent_memory.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        context = mod.gather_context(self.run_dir)
        self.assertGreater(len(context), 0)
        sources = [c["source"] for c in context]
        self.assertIn("thinking_plan.md", sources)


class TestUpdateMemoryFromRuns(unittest.TestCase):
    """Tests for update_memory_from_runs.py."""

    def test_main_returns_zero_on_success(self):
        """main() returns 0 when memory validation succeeds."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "update_memory_from_runs.py")],
            capture_output=True, text=True,
        )
        # Should succeed (memory validation passes)
        self.assertEqual(result.returncode, 0, result.stderr)


class TestCheckMatrix(unittest.TestCase):
    """Tests for check_matrix.py."""

    def test_check_matrix_loads(self):
        """check_matrix.py can be imported without errors."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "check_matrix", RUNTIME / "check_matrix.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, "main"))


class TestAdversarialLoop(unittest.TestCase):
    """Tests for adversarial_loop.py."""

    def test_adversarial_loop_loads(self):
        """adversarial_loop.py can be imported without errors."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "adversarial_loop", RUNTIME / "adversarial_loop.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, "main"))


class TestContextEngineer(unittest.TestCase):
    """Tests for context_engineer.py."""

    def test_context_engineer_loads(self):
        """context_engineer.py can be imported without errors."""
        import importlib.util
        import sys
        runtime_dir = str(RUNTIME)
        if runtime_dir not in sys.path:
            sys.path.insert(0, runtime_dir)
        spec = importlib.util.spec_from_file_location(
            "context_engineer", RUNTIME / "context_engineer.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # context_engineer.py has enrich_prompt, not main
        self.assertTrue(hasattr(mod, "enrich_prompt") or hasattr(mod, "main"))


class TestContextInjector(unittest.TestCase):
    """Tests for context_injector.py."""

    def test_context_injector_loads(self):
        """context_injector.py can be imported without errors."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "context_injector", RUNTIME / "context_injector.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # context_injector.py has enrich_prompt_with_context, not main
        self.assertTrue(hasattr(mod, "enrich_prompt_with_context") or hasattr(mod, "main"))


if __name__ == "__main__":
    unittest.main()
