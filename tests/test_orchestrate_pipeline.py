"""Tests for .agentic-pi/runtime/orchestrate_pipeline.py.

Covers:
- run_phase: subprocess execution, failure handling, output printing
- main: phase ordering, init_run skip, error handling, exit codes
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".agentic-pi" / "runtime"
ORCHESTRATE_PATH = RUNTIME / "orchestrate_pipeline.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("orchestrate_pipeline", ORCHESTRATE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestRunPhase(unittest.TestCase):
    """Test run_phase function."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_raises_on_missing_script(self):
        """run_phase raises RuntimeError if script doesn't exist."""
        with self.assertRaises(RuntimeError) as ctx:
            self.mod.run_phase(Path("/nonexistent/script.py"), "Test Phase")
        self.assertIn("not found", str(ctx.exception))

    def test_raises_on_nonzero_exit(self):
        """run_phase raises RuntimeError if script returns non-zero."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("import sys; sys.exit(1)\n")
            f.flush()
            script = Path(f.name)

        try:
            with self.assertRaises(RuntimeError) as ctx:
                self.mod.run_phase(script, "Failing Phase")
            self.assertIn("failed with code 1", str(ctx.exception))
        finally:
            script.unlink()

    def test_succeeds_on_zero_exit(self):
        """run_phase completes without error on zero exit."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("print('success')\n")
            f.flush()
            script = Path(f.name)

        try:
            # Should not raise
            self.mod.run_phase(script, "Passing Phase")
        finally:
            script.unlink()

    def test_passes_extra_args(self):
        """run_phase passes extra_args to the subprocess."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("import sys; print(' '.join(sys.argv[1:]))\n")
            f.flush()
            script = Path(f.name)

        try:
            # Should not raise — just verify it runs
            self.mod.run_phase(script, "Args Phase", ["--flag", "value"])
        finally:
            script.unlink()

    def test_uses_sys_executable(self):
        """run_phase uses sys.executable to run scripts."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            script = Path(__file__)  # any existing file
            self.mod.run_phase(script, "Test Phase")
            call_args = mock_run.call_args
            self.assertEqual(call_args[0][0][0], sys.executable)


class TestMain(unittest.TestCase):
    """Test main function."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_returns_zero_on_success(self):
        """main returns 0 when all phases succeed."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            with patch("sys.argv", ["orchestrate_pipeline.py", "--run-id", "test_run"]):
                with patch.object(Path, "is_file", return_value=True):
                    with patch.object(Path, "is_dir", return_value=False):
                        with patch.object(Path, "exists", return_value=False):
                            result = self.mod.main()
                            self.assertEqual(result, 0)

    def test_returns_one_on_phase_failure(self):
        """main returns 1 when a phase fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="error")
            with patch("sys.argv", ["orchestrate_pipeline.py", "--run-id", "test_run"]):
                with patch.object(Path, "is_file", return_value=True):
                    with patch.object(Path, "is_dir", return_value=False):
                        with patch.object(Path, "exists", return_value=False):
                            result = self.mod.main()
                            self.assertEqual(result, 1)

    def test_skips_init_run_when_dir_exists(self):
        """init_run phase is skipped when run directory already exists."""
        call_count = [0]

        def mock_subprocess_run(cmd, **kwargs):
            call_count[0] += 1
            return MagicMock(returncode=0, stdout="")

        with patch("subprocess.run", side_effect=mock_subprocess_run):
            with patch("sys.argv", ["orchestrate_pipeline.py", "--run-id", "test_run"]):
                with patch.object(Path, "is_file", return_value=True):
                    with patch.object(Path, "is_dir", return_value=True):
                        with patch.object(Path, "exists", return_value=False):
                            with patch("builtins.print") as mock_print:
                                result = self.mod.main()
                                # Check that init_run was skipped
                                printed = [str(c) for c in mock_print.call_args_list]
                                skipped = any("skipped" in str(c) for c in printed)
                                self.assertTrue(skipped)

    def test_phase_order_is_correct(self):
        """Phases run in the correct order: init, linker, graph, verifier, signing, certifier."""
        phase_order = []

        def mock_subprocess_run(cmd, **kwargs):
            # Extract phase name from the command
            for arg in cmd:
                if "init_run" in str(arg):
                    phase_order.append("init_run")
                elif "artifact_linker" in str(arg):
                    phase_order.append("artifact_linker")
                elif "task_graph_builder" in str(arg):
                    phase_order.append("task_graph_builder")
                elif "harness_contract_verifier" in str(arg):
                    phase_order.append("harness_contract_verifier")
                elif "harness_signing" in str(arg):
                    phase_order.append("harness_signing")
                elif "certify_run" in str(arg):
                    phase_order.append("certify_run")
            return MagicMock(returncode=0, stdout="")

        with patch("subprocess.run", side_effect=mock_subprocess_run):
            with patch("sys.argv", ["orchestrate_pipeline.py", "--run-id", "test_run"]):
                with patch.object(Path, "is_file", return_value=True):
                    with patch.object(Path, "is_dir", return_value=False):
                        with patch.object(Path, "exists", return_value=False):
                            self.mod.main()

        expected_order = [
            "init_run",
            "artifact_linker",
            "task_graph_builder",
            "harness_contract_verifier",
            "harness_signing",
            "certify_run",
        ]
        self.assertEqual(phase_order, expected_order)

    def test_aborts_on_first_failure(self):
        """Pipeline aborts on first phase failure, doesn't continue."""
        phase_count = [0]

        def mock_subprocess_run(cmd, **kwargs):
            phase_count[0] += 1
            if phase_count[0] == 2:  # Second phase fails
                return MagicMock(returncode=1, stdout="error")
            return MagicMock(returncode=0, stdout="")

        with patch("subprocess.run", side_effect=mock_subprocess_run):
            with patch("sys.argv", ["orchestrate_pipeline.py", "--run-id", "test_run"]):
                with patch.object(Path, "is_file", return_value=True):
                    with patch.object(Path, "is_dir", return_value=False):
                        with patch.object(Path, "exists", return_value=False):
                            result = self.mod.main()
                            self.assertEqual(result, 1)
                            # Should have stopped after 2 phases (init + failed artifact_linker)
                            self.assertEqual(phase_count[0], 2)


if __name__ == "__main__":
    unittest.main()
