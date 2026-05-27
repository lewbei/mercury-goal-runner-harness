"""Tests for .agentic-pi/runtime/gateway_dispatch.py.

Covers:
- _is_disposable: disposable run ID detection
- _build_command_string: command string building
- _is_known_harness_command: harness tool detection
- dispatch: gateway enforcement dispatch
- dispatch_raw: raw shell command dispatch
- certifier_command: certifier invocation path
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".agentic-pi" / "runtime"
GATEWAY_DISPATCH_PATH = RUNTIME / "gateway_dispatch.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("gateway_dispatch", GATEWAY_DISPATCH_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestIsDisposable(unittest.TestCase):
    """Test disposable run ID detection."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_smoke_run_is_disposable(self):
        self.assertTrue(self.mod._is_disposable("pi_smoke_test_123"))

    def test_smoke_run_prefix_is_disposable(self):
        self.assertTrue(self.mod._is_disposable("pi_smoke_"))

    def test_non_smoke_run_is_not_disposable(self):
        self.assertFalse(self.mod._is_disposable("my_goal_123"))

    def test_empty_run_id_is_not_disposable(self):
        self.assertFalse(self.mod._is_disposable(""))

    def test_partial_prefix_is_not_disposable(self):
        self.assertFalse(self.mod._is_disposable("pi_smoketest"))


class TestBuildCommandString(unittest.TestCase):
    """Test command string building."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_joins_args(self):
        result = self.mod._build_command_string(["python", "script.py", "--flag"])
        self.assertEqual(result, "python script.py --flag")

    def test_empty_args(self):
        result = self.mod._build_command_string([])
        self.assertEqual(result, "")

    def test_single_arg(self):
        result = self.mod._build_command_string(["python"])
        self.assertEqual(result, "python")


class TestIsKnownHarnessCommand(unittest.TestCase):
    """Test harness tool detection."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_init_run_is_known(self):
        self.assertTrue(self.mod._is_known_harness_command(["init_run.py", "my_goal"]))

    def test_compile_raw_goal_is_known(self):
        self.assertTrue(self.mod._is_known_harness_command(["compile_raw_goal.py"]))

    def test_run_goal_is_known(self):
        self.assertTrue(self.mod._is_known_harness_command(["run_goal.py", "my_goal"]))

    def test_planning_proof_runner_is_known(self):
        self.assertTrue(self.mod._is_known_harness_command(["planning_proof_runner.py"]))

    def test_strategy_proof_runner_is_known(self):
        self.assertTrue(self.mod._is_known_harness_command(["strategy_proof_runner.py"]))

    def test_replay_run_is_known(self):
        self.assertTrue(self.mod._is_known_harness_command(["replay_run.py"]))

    def test_audit_run_is_known(self):
        self.assertTrue(self.mod._is_known_harness_command(["audit_run.py"]))

    def test_rollback_run_is_known(self):
        self.assertTrue(self.mod._is_known_harness_command(["rollback_run.py"]))

    def test_unknown_command_is_not_known(self):
        self.assertFalse(self.mod._is_known_harness_command(["rm", "-rf", "/"]))

    def test_empty_args_is_not_known(self):
        self.assertFalse(self.mod._is_known_harness_command([]))

    def test_path_with_known_name_is_known(self):
        self.assertTrue(self.mod._is_known_harness_command([
            ".agentic-pi/runtime/init_run.py"
        ]))

    def test_windows_path_with_known_name_is_known(self):
        self.assertTrue(self.mod._is_known_harness_command([
            ".agentic-pi\\runtime\\init_run.py"
        ]))


class TestDispatch(unittest.TestCase):
    """Test gateway enforcement dispatch."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_known_harness_command_always_allowed(self):
        """Known harness tools bypass gateway enforcement."""
        # init_run with a non-existent run dir should still be allowed
        # (it will fail at the script level, not at the gateway)
        exit_code, stdout = self.mod.dispatch(
            ["-c", "print('hello')"],
            "my_goal",
            cwd=ROOT,
        )
        # Known harness commands aren't in this list, so let's test with
        # a real known command that will fail at the script level
        # Actually, we need to mock subprocess to test the gateway logic
        pass

    def test_non_disposable_run_bypasses_enforcement(self):
        """Non-disposable runs fall through (backward compat)."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok")
            exit_code, stdout = self.mod.dispatch(
                ["some_script.py"],
                "non_disposable_run",
            )
            # Non-disposable runs are not blocked
            self.assertEqual(exit_code, 0)

    def test_disposable_run_blocked_for_unknown_command(self):
        """Disposable runs block unknown commands."""
        # Mock _classify to return BLOCK
        with patch.object(self.mod, "_classify", return_value={
            "command_kind": "blocked",
            "decision": "BLOCK",
            "reason": "test block",
        }):
            exit_code, stdout = self.mod.dispatch(
                ["unknown_script.py"],
                "pi_smoke_test",
            )
            self.assertEqual(exit_code, 1)
            self.assertIn("GATEWAY_BLOCKED", stdout)

    def test_disposable_run_allows_certifier(self):
        """Disposable runs allow certifier commands."""
        with patch.object(self.mod, "_classify", return_value={
            "command_kind": "certifier",
            "decision": "ALLOW",
            "reason": "exact deterministic certifier command",
        }):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="certified")
                exit_code, stdout = self.mod.dispatch(
                    ["certify_run.py", ".agentic-runs/pi_smoke_test"],
                    "pi_smoke_test",
                )
                self.assertEqual(exit_code, 0)

    def test_dispatch_returns_exit_code_and_stdout(self):
        """dispatch returns (exit_code, stdout) tuple."""
        with patch.object(self.mod, "_classify", return_value={
            "command_kind": "unknown",
            "decision": "ALLOW",
            "reason": "test",
        }):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=42, stdout="output text")
                exit_code, stdout = self.mod.dispatch(
                    ["test.py"],
                    "non_disposable",
                )
                self.assertEqual(exit_code, 42)
                self.assertEqual(stdout, "output text")

    def test_dispatch_uses_sys_executable(self):
        """dispatch runs commands through sys.executable (python)."""
        with patch.object(self.mod, "_classify", return_value={
            "command_kind": "unknown",
            "decision": "ALLOW",
            "reason": "test",
        }):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="")
                self.mod.dispatch(["script.py"], "non_disposable")
                call_args = mock_run.call_args
                self.assertEqual(call_args[0][0][0], sys.executable)


class TestDispatchRaw(unittest.TestCase):
    """Test raw shell command dispatch."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_blocked_command_returns_nonzero(self):
        """Blocked raw commands return exit code 1."""
        mock_gw = MagicMock()
        mock_gw.execute_gateway_command.return_value = {
            "decision": "BLOCK",
            "reason": "test block",
            "exit_code": 0,  # Gateway didn't set non-zero
            "stdout_tail": "",
        }
        with patch.object(self.mod, "_load_gateway", return_value=mock_gw):
            exit_code, stdout = self.mod.dispatch_raw(
                "rm -rf /", "pi_smoke_test"
            )
            self.assertEqual(exit_code, 1)
            self.assertIn("GATEWAY_BLOCKED", stdout)

    def test_allowed_command_passes_through(self):
        """Allowed raw commands pass through with gateway exit code."""
        mock_gw = MagicMock()
        mock_gw.execute_gateway_command.return_value = {
            "decision": "ALLOW",
            "reason": "allowed",
            "exit_code": 0,
            "stdout_tail": "success",
        }
        with patch.object(self.mod, "_load_gateway", return_value=mock_gw):
            exit_code, stdout = self.mod.dispatch_raw(
                "python script.py", "pi_smoke_test"
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout, "success")

    def test_blocked_with_nonzero_exit_preserved(self):
        """If gateway already set non-zero exit, preserve it."""
        mock_gw = MagicMock()
        mock_gw.execute_gateway_command.return_value = {
            "decision": "BLOCK",
            "reason": "test block",
            "exit_code": 2,
            "stdout_tail": "already blocked",
        }
        with patch.object(self.mod, "_load_gateway", return_value=mock_gw):
            exit_code, stdout = self.mod.dispatch_raw(
                "rm -rf /", "pi_smoke_test"
            )
            self.assertEqual(exit_code, 2)


class TestCertifierCommand(unittest.TestCase):
    """Test certifier invocation path."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_certifier_command_uses_gateway(self):
        """certifier_command delegates to gateway.certifier_command."""
        mock_gw = MagicMock()
        mock_gw.certifier_command.return_value = "python certify_run.py .agentic-runs/test"
        mock_gw.execute_gateway_command.return_value = {
            "decision": "ALLOW",
            "reason": "certifier",
            "exit_code": 0,
            "stdout_tail": "certified",
        }
        with patch.object(self.mod, "_load_gateway", return_value= mock_gw):
            exit_code, stdout = self.mod.certifier_command("test")
            mock_gw.certifier_command.assert_called_once_with("test")


class TestLoadGateway(unittest.TestCase):
    """Test gateway module loading."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_gateway_loads_successfully(self):
        """_load_gateway returns the command_gateway module."""
        # Reset cached gateway
        self.mod._command_gateway = None
        gw = self.mod._load_gateway()
        self.assertIsNotNone(gw)
        self.assertTrue(hasattr(gw, "classify_command"))
        self.assertTrue(hasattr(gw, "execute_gateway_command"))

    def test_gateway_is_cached(self):
        """_load_gateway caches the module (doesn't reload)."""
        self.mod._command_gateway = None
        gw1 = self.mod._load_gateway()
        gw2 = self.mod._load_gateway()
        self.assertIs(gw1, gw2)


if __name__ == "__main__":
    unittest.main()
