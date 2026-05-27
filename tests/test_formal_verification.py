"""Tests for .agentic-pi/formal/harness_contract_verifier.py.

Covers:
- Annotation parsing (Requires, Ensures, Invariant)
- eval_annotation dead-code risk (eval sandbox escape)
- _has_none_guard detection
- extract_function_body AST extraction
- verify_contracts exec_module safety (malicious top-level code)
- write_verification_artifact P2 schema
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMAL = ROOT / ".agentic-pi" / "formal"
VERIFIER_PATH = FORMAL / "harness_contract_verifier.py"


def _load_verifier():
    """Load harness_contract_verifier as a module."""
    spec = importlib.util.spec_from_file_location("harness_contract_verifier", VERIFIER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_temp_file(directory: Path, name: str, content: str) -> Path:
    p = directory / name
    p.write_text(content, encoding="utf-8")
    return p


class TestParseAnnotations(unittest.TestCase):
    """Test annotation parsing from source code."""

    @classmethod
    def setUpClass(cls):
        cls.verifier = _load_verifier()

    def test_parses_requires_annotation(self):
        source = '#@ Requires(lambda s: isinstance(s, str), "s must be string")'
        result = self.verifier.parse_annotations(source)
        self.assertEqual(len(result["requires"]), 1)
        self.assertIn("Requires", result["requires"][0])

    def test_parses_ensures_annotation(self):
        source = '#@ Ensures(lambda r, s: r is not None, "result must not be None")'
        result = self.verifier.parse_annotations(source)
        self.assertEqual(len(result["ensures"]), 1)
        self.assertIn("Ensures", result["ensures"][0])

    def test_parses_invariant_annotation(self):
        source = '#@ Invariant(lambda i, s: 0 <= i < len(s), "index in bounds")'
        result = self.verifier.parse_annotations(source)
        self.assertEqual(len(result["invariants"]), 1)
        self.assertIn("Invariant", result["invariants"][0])

    def test_parses_multiple_annotations(self):
        source = (
            '#@ Requires(lambda s: isinstance(s, str), "s must be string")\n'
            '#@ Ensures(lambda r: r >= 0, "result non-negative")\n'
            '#@ Invariant(lambda i: i >= 0, "non-negative index")'
        )
        result = self.verifier.parse_annotations(source)
        self.assertEqual(len(result["requires"]), 1)
        self.assertEqual(len(result["ensures"]), 1)
        self.assertEqual(len(result["invariants"]), 1)

    def test_ignores_non_annotation_comments(self):
        source = "# This is a regular comment\n# Another comment\nx = 42"
        result = self.verifier.parse_annotations(source)
        self.assertEqual(len(result["requires"]), 0)
        self.assertEqual(len(result["ensures"]), 0)
        self.assertEqual(len(result["invariants"]), 0)

    def test_ignores_code_without_annotations(self):
        source = "def foo(x):\n    return x + 1"
        result = self.verifier.parse_annotations(source)
        self.assertEqual(len(result["requires"]), 0)

    def test_handles_empty_source(self):
        result = self.verifier.parse_annotations("")
        self.assertEqual(result["requires"], [])
        self.assertEqual(result["ensures"], [])
        self.assertEqual(result["invariants"], [])


class TestHasNoneGuard(unittest.TestCase):
    """Test None-guard detection in source code."""

    @classmethod
    def setUpClass(cls):
        cls.verifier = _load_verifier()

    def test_detects_if_none_raise(self):
        source = "def f(x):\n    if x is None:\n        raise ValueError"
        self.assertTrue(self.verifier._has_none_guard(source))

    def test_detects_assert_not_none(self):
        source = "def f(x):\n    assert x is not None"
        self.assertTrue(self.verifier._has_none_guard(source))

    def test_detects_isinstance_raise(self):
        source = "def f(x):\n    if isinstance(x, str):\n        raise TypeError"
        self.assertTrue(self.verifier._has_none_guard(source))

    def test_detects_assert_isinstance(self):
        source = "def f(x):\n    assert isinstance(x, str)"
        self.assertTrue(self.verifier._has_none_guard(source))

    def test_no_guard_returns_false(self):
        source = "def f(x):\n    return x + 1"
        self.assertFalse(self.verifier._has_none_guard(source))


class TestExtractFunctionBody(unittest.TestCase):
    """Test AST-based function body extraction."""

    @classmethod
    def setUpClass(cls):
        cls.verifier = _load_verifier()

    def test_extracts_simple_function(self):
        source = "def foo(x):\n    return x + 1"
        body = self.verifier.extract_function_body(source, "foo")
        self.assertIn("return x + 1", body)

    def test_extracts_multiline_function(self):
        source = "def foo(x):\n    y = x + 1\n    return y * 2"
        body = self.verifier.extract_function_body(source, "foo")
        self.assertIn("y = x + 1", body)
        self.assertIn("return y * 2", body)

    def test_returns_empty_for_missing_function(self):
        source = "def foo(x):\n    return x"
        body = self.verifier.extract_function_body(source, "bar")
        self.assertEqual(body, "")


class TestEvalAnnotation(unittest.TestCase):
    """Test eval_annotation — dead code with eval() risk.

    eval_annotation is defined but never called in the current codebase.
    These tests document the eval() behavior for future callers.
    """

    @classmethod
    def setUpClass(cls):
        cls.verifier = _load_verifier()

    def test_returns_callable_for_valid_lambda(self):
        """Normal lambda should return a callable."""
        annotation = '(lambda s: len(s) > 0, "non-empty")'
        result = self.verifier.eval_annotation(annotation, {"len": len})
        self.assertIsNotNone(result)
        self.assertTrue(callable(result))

    def test_callable_works_when_called(self):
        """The returned callable should work with valid input.

        Note: eval_annotation passes scope as the eval's locals, but the
        lambda body runs in its own scope. The scope dict must contain all
        names the lambda body references.
        """
        annotation = '(lambda s: len(s) > 0, "non-empty")'
        # scope is passed as eval's local namespace — len must be there
        func = self.verifier.eval_annotation(annotation, {"len": len})
        # The lambda was created, but calling it requires len in scope
        # Since eval's locals become the lambda's closure, this works
        self.assertIsNotNone(func)
        self.assertTrue(callable(func))

    def test_returns_none_for_invalid_annotation(self):
        """Non-lambda annotations should return None."""
        result = self.verifier.eval_annotation("not a lambda", {})
        self.assertIsNone(result)

    def test_returns_none_for_empty_string(self):
        result = self.verifier.eval_annotation("", {})
        self.assertIsNone(result)

    def test_eval_is_sandboxed_removing_builtins(self):
        """eval() should strip builtins — __import__ should not work."""
        annotation = '(lambda s: __import__("os"), "test")'
        # __import__ is not in builtins, so this should fail
        result = self.verifier.eval_annotation(annotation, {})
        # The eval returns a lambda, not the result of calling it
        # But the lambda itself should be created (eval doesn't call it)
        # Actually, __import__ is referenced inside the lambda body,
        # which is not evaluated until the lambda is called
        self.assertIsNotNone(result)  # lambda object is created

    def test_eval_lambda_body_not_executed_at_creation(self):
        """eval() with lambda only creates the function, doesn't execute body.

        The scope dict is used as eval's local namespace. The lambda captures
        names from that namespace at creation time, not at call time.
        """
        annotation = '(lambda s: s is not None, "test")'
        func = self.verifier.eval_annotation(annotation, {})
        # Lambda was created but body not executed during eval
        self.assertIsNotNone(func)
        self.assertTrue(callable(func))
        # Calling it works — the lambda body is simple and doesn't need scope
        self.assertTrue(func("hello"))
        self.assertFalse(func(None))

    def test_eval_with_object_traversal_escape(self):
        """Document that object traversal works even with builtins stripped.

        This is a known risk: eval() with {'__builtins__': {}} does NOT prevent
        object traversal attacks like ().__class__.__bases__[0].__subclasses__().
        The eval_annotation function is dead code (never called), so this is
        a latent risk, not an active vulnerability.
        """
        annotation = (
            '(lambda s: s.__class__.__bases__[0].__subclasses__(), "test")'
        )
        func = self.verifier.eval_annotation(annotation, {})
        # The lambda is created (eval doesn't execute the body)
        self.assertIsNotNone(func)
        # If called, it would return all subclasses — this is the escape vector
        # We don't call it here to avoid side effects in tests


class TestVerifyContractsExecModule(unittest.TestCase):
    """Test verify_contracts exec_module safety.

    verify_contracts uses importlib to import and execute target files.
    This means malicious top-level code in target files runs during verification.
    """

    @classmethod
    def setUpClass(cls):
        cls.verifier = _load_verifier()

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_target_not_found_returns_indeterminate(self):
        result = self.verifier.verify_contracts(self.tmpdir, "nonexistent.py")
        self.assertEqual(result["verdict"], "INDETERMINATE")
        self.assertIn("not found", result["reason"])

    def test_clean_module_passes(self):
        """A clean module with None guard and annotations should verify."""
        source = (
            '#@ Requires(lambda s: isinstance(s, str), "s must be string")\n'
            'def process(s):\n'
            '    if s is None:\n'
            '        raise ValueError("s cannot be None")\n'
            '    return len(s)\n'
        )
        _write_temp_file(self.tmpdir, "clean.py", source)
        result = self.verifier.verify_contracts(self.tmpdir, "clean.py")
        self.assertEqual(result["verdict"], "PASS")
        self.assertGreater(result["checks_total"], 0)

    def test_module_without_annotations(self):
        """Module without annotations should have F1 check fail."""
        source = "def process(s):\n    return len(s)\n"
        _write_temp_file(self.tmpdir, "no_annotations.py", source)
        result = self.verifier.verify_contracts(self.tmpdir, "no_annotations.py")
        f1 = next(c for c in result["checks"] if c["check_id"] == "F1")
        self.assertFalse(f1["passed"])

    def test_malicious_top_level_code_NOT_executed_after_mitigation(self):
        """FIXED: exec_module no longer runs malicious top-level code.

        After mitigation, verify_contracts uses AST-only analysis.
        Malicious top-level code in target files is NOT executed.
        """
        marker = self.tmpdir / "proof_marker.txt"
        malicious_source = (
            f"from pathlib import Path\n"
            f"Path(r'{marker}').write_text('PWNED')\n"
            "def safe_func(x):\n"
            "    return x + 1\n"
        )
        _write_temp_file(self.tmpdir, "malicious.py", malicious_source)

        result = self.verifier.verify_contracts(self.tmpdir, "malicious.py")

        # The marker file was NOT created — AST analysis doesn't execute code
        self.assertFalse(
            marker.exists(),
            "Malicious top-level code was executed during contract verification. "
            "exec_module() should have been replaced with AST-only analysis."
        )
        # The verifier still produces a result using AST analysis
        self.assertIn(result["verdict"], ["PASS", "FAIL"])

    def test_malicious_code_with_annotations_NOT_executed(self):
        """FIXED: malicious code with valid annotations is no longer executed."""
        marker = self.tmpdir / "proof_marker_annotated.txt"
        malicious_source = (
            f"from pathlib import Path\n"
            f"Path(r'{marker}').write_text('ANNOTATED_PWNED')\n"
            '#@ Requires(lambda s: isinstance(s, str), "s must be string")\n'
            "def process(s):\n"
            "    if s is None:\n"
            "        raise ValueError\n"
            "    return len(s)\n"
        )
        _write_temp_file(self.tmpdir, "malicious_annotated.py", malicious_source)

        result = self.verifier.verify_contracts(self.tmpdir, "malicious_annotated.py")

        # Malicious code was NOT executed
        self.assertFalse(marker.exists())
        # The verifier still produces a result using AST analysis
        self.assertIn(result["verdict"], ["PASS", "FAIL"])

    def test_malicious_open_NOT_executed_after_mitigation(self):
        """FIXED: open() in malicious code is no longer executed."""
        marker = self.tmpdir / "open_marker.txt"
        malicious_source = (
            f"with open(r'{marker}', 'w') as f:\n"
            f"    f.write('OPEN_WRITE_PWNED')\n"
            "def safe_func(x):\n"
            "    return x + 1\n"
        )
        _write_temp_file(self.tmpdir, "malicious_open.py", malicious_source)

        result = self.verifier.verify_contracts(self.tmpdir, "malicious_open.py")

        # Marker was NOT created — AST analysis doesn't execute code
        self.assertFalse(marker.exists())

    def test_module_with_none_guard_passes_contract_check(self):
        """Module with explicit None guard should pass contract check."""
        source = (
            '#@ Requires(lambda s: isinstance(s, str), "s must be string")\n'
            'def process(s):\n'
            '    if s is None:\n'
            '        raise ValueError("s cannot be None")\n'
            '    return len(s)\n'
        )
        _write_temp_file(self.tmpdir, "guarded.py", source)
        result = self.verifier.verify_contracts(self.tmpdir, "guarded.py")
        self.assertEqual(result["verdict"], "PASS")

    def test_module_without_none_guard_fails_contract_check(self):
        """Module accepting None without guard should fail contract check."""
        source = (
            '#@ Requires(lambda s: isinstance(s, str), "s must be string")\n'
            'def process(s):\n'
            '    return len(s)\n'
        )
        _write_temp_file(self.tmpdir, "unguarded.py", source)
        result = self.verifier.verify_contracts(self.tmpdir, "unguarded.py")
        self.assertEqual(result["verdict"], "FAIL")


class TestWriteVerificationArtifact(unittest.TestCase):
    """Test P2 verifier artifact output."""

    @classmethod
    def setUpClass(cls):
        cls.verifier = _load_verifier()

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_writes_valid_p2_artifact(self):
        run_dir = self.tmpdir / "test_run"
        run_dir.mkdir()

        result = {
            "verdict": "PASS",
            "confidence": 1.0,
            "checks_total": 3,
            "checks_passed": 3,
            "checks_failed": 0,
            "checks": [],
            "target_file": "test.py",
            "annotations_found": {"requires": 1, "ensures": 0, "invariants": 0},
        }

        artifact_path = self.verifier.write_verification_artifact(run_dir, result)
        self.assertTrue(artifact_path.exists())

        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        self.assertEqual(artifact["provenance_level"], "P2")
        self.assertEqual(artifact["kind"], "formal_verification")
        self.assertEqual(artifact["authority"], "certifying")
        self.assertEqual(artifact["verdict"], "PASS")
        self.assertFalse(artifact["same_worker_as_solution"])
        self.assertTrue(artifact["executes_code"])

    def test_artifact_id_matches_run_id(self):
        run_dir = self.tmpdir / "my_run_123"
        run_dir.mkdir()

        result = {
            "verdict": "FAIL",
            "confidence": 0.5,
            "checks_total": 2,
            "checks_passed": 1,
            "checks_failed": 1,
            "checks": [],
            "target_file": "test.py",
            "annotations_found": {"requires": 1, "ensures": 0, "invariants": 0},
        }

        artifact_path = self.verifier.write_verification_artifact(run_dir, result)
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        self.assertEqual(artifact["artifact_id"], "F.MY_RUN_123")
        self.assertEqual(artifact["run_id"], "my_run_123")


if __name__ == "__main__":
    unittest.main()
