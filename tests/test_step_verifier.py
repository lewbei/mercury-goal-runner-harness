#!/usr/bin/env python3
"""Tests for step-level verification and replanning."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agentic-pi" / "runtime"))


class TestStepVerifier(unittest.TestCase):
    """Test step_verifier.py."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.run_dir = Path(self.tmpdir) / "test_run"
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_merged_plan(self, steps=None):
        """Write a merged_plan.json."""
        if steps is None:
            steps = [
                {"step_id": 1, "action": "create_file", "path": "hello.py", "content": "print('Hello')"},
                {"step_id": 2, "action": "create_file", "path": "README.md", "content": "# Hello"},
            ]
        (self.run_dir / "merged_plan.json").write_text(json.dumps({"steps": steps}))

    def _write_file(self, path, content):
        """Write a file."""
        full_path = self.run_dir / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    def test_no_merged_plan(self):
        """Test verification with no merged_plan.json."""
        from step_verifier import run_step_verification
        result = run_step_verification(self.run_dir, 1)
        self.assertIsNotNone(result.get("error"))

    def test_step_not_found(self):
        """Test verification with step not found."""
        from step_verifier import run_step_verification
        self._write_merged_plan()
        result = run_step_verification(self.run_dir, 99)
        self.assertIsNotNone(result.get("error"))

    def test_file_missing(self):
        """Test verification when file is missing."""
        from step_verifier import run_step_verification
        self._write_merged_plan()
        result = run_step_verification(self.run_dir, 1)
        self.assertTrue(result["needs_replanning"])
        self.assertIn("file_exists", [c["check"] for c in result["verification"]["checks"]])

    def test_file_exists(self):
        """Test verification when file exists."""
        from step_verifier import run_step_verification
        self._write_merged_plan()
        self._write_file("hello.py", "print('Hello')")
        result = run_step_verification(self.run_dir, 1)
        self.assertFalse(result["needs_replanning"])
        file_check = next(c for c in result["verification"]["checks"] if c["check"] == "file_exists")
        self.assertTrue(file_check["passed"])

    def test_python_syntax_valid(self):
        """Test verification with valid Python syntax."""
        from step_verifier import run_step_verification
        self._write_merged_plan()
        self._write_file("hello.py", "print('Hello')")
        result = run_step_verification(self.run_dir, 1)
        syntax_check = next(c for c in result["verification"]["checks"] if c["check"] == "python_syntax")
        self.assertTrue(syntax_check["passed"])

    def test_python_syntax_invalid(self):
        """Test verification with invalid Python syntax."""
        from step_verifier import run_step_verification
        self._write_merged_plan()
        self._write_file("hello.py", "print('Hello'")  # Missing closing paren
        result = run_step_verification(self.run_dir, 1)
        self.assertTrue(result["needs_replanning"])
        syntax_check = next(c for c in result["verification"]["checks"] if c["check"] == "python_syntax")
        self.assertFalse(syntax_check["passed"])

    def test_json_valid(self):
        """Test verification with valid JSON."""
        from step_verifier import run_step_verification
        steps = [
            {"step_id": 1, "action": "create_file", "path": "config.json", "content": '{"key": "value"}'},
        ]
        self._write_merged_plan(steps)
        self._write_file("config.json", '{"key": "value"}')
        result = run_step_verification(self.run_dir, 1)
        json_check = next(c for c in result["verification"]["checks"] if c["check"] == "json_valid")
        self.assertTrue(json_check["passed"])

    def test_json_invalid(self):
        """Test verification with invalid JSON."""
        from step_verifier import run_step_verification
        steps = [
            {"step_id": 1, "action": "create_file", "path": "config.json", "content": '{"key": "value"'},
        ]
        self._write_merged_plan(steps)
        self._write_file("config.json", '{"key": "value"')  # Missing closing brace
        result = run_step_verification(self.run_dir, 1)
        self.assertTrue(result["needs_replanning"])
        json_check = next(c for c in result["verification"]["checks"] if c["check"] == "json_valid")
        self.assertFalse(json_check["passed"])

    def test_suggestions_generated(self):
        """Test that suggestions are generated for issues."""
        from step_verifier import run_step_verification
        self._write_merged_plan()
        result = run_step_verification(self.run_dir, 1)
        self.assertTrue(len(result["suggestions"]) > 0)
        self.assertIn("action", result["suggestions"][0])

    def test_multiple_steps(self):
        """Test verification with multiple steps."""
        from step_verifier import run_step_verification
        self._write_merged_plan()
        self._write_file("hello.py", "print('Hello')")
        self._write_file("README.md", "# Hello")
        
        result1 = run_step_verification(self.run_dir, 1)
        result2 = run_step_verification(self.run_dir, 2)
        
        self.assertFalse(result1["needs_replanning"])
        self.assertFalse(result2["needs_replanning"])


if __name__ == "__main__":
    unittest.main()
