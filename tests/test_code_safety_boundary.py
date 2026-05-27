"""Boundary scanner: detect dangerous code patterns in harness code.

Scans .agentic-pi/ and tests/ for:
- eval() / exec() usage (code injection risk)
- os.system() / os.popen() usage (shell injection risk)
- subprocess with shell=True (shell injection risk)

Known exceptions are allowlisted with documented reasons.
docs/ is excluded — it may reference these patterns by design.
"""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Directories to scan (relative to ROOT)
SCAN_DIRS = [".agentic-pi", "tests"]

# Files that are allowlisted for specific dangerous patterns.
# Each entry: (relative_path, pattern_name, reason)
ALLOWLIST = [
    (
        ".agentic-pi/formal/harness_contract_verifier.py",
        "eval",
        "Dead code: eval_annotation() is defined but never called. "
        "Latent risk documented in test_formal_verification.py.",
    ),
]


def _iter_python_files():
    """Yield all .py files under SCAN_DIRS, skipping __pycache__."""
    for scan_dir in SCAN_DIRS:
        target = ROOT / scan_dir
        if not target.exists():
            continue
        for path in target.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            yield path


def _is_allowlisted(filepath: Path, pattern_name: str) -> bool:
    """Check if a file+pattern combination is allowlisted."""
    rel = str(filepath.relative_to(ROOT)).replace("\\", "/")
    return any(
        rel == entry[0] and pattern_name == entry[1]
        for entry in ALLOWLIST
    )


def _check_dangerous_calls(filepath: Path) -> list[str]:
    """Return list of violations from dangerous function calls.

    Uses AST to find calls to eval(), exec(), os.system(), os.popen(),
    and subprocess.run/Popen/call with shell=True.
    """
    violations = []
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return violations

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        call_name = None

        # eval(...) or exec(...)
        if isinstance(func, ast.Name):
            if func.id in ("eval", "exec"):
                call_name = func.id

        # os.system(...), os.popen(...)
        elif isinstance(func, ast.Attribute):
            if func.attr in ("system", "popen"):
                call_name = f"os.{func.attr}"

        if call_name and not _is_allowlisted(filepath, call_name):
            violations.append(
                f"line {node.lineno}: {call_name}() call"
            )

    return violations


def _check_shell_true(filepath: Path) -> list[str]:
    """Return list of subprocess calls with shell=True."""
    violations = []
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return violations

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        is_subprocess = False

        # subprocess.run(...), subprocess.Popen(...), subprocess.call(...)
        if isinstance(func, ast.Attribute) and func.attr in (
            "run", "Popen", "call", "check_call", "check_output"
        ):
            if isinstance(func.value, ast.Name) and func.value.id == "subprocess":
                is_subprocess = True

        if is_subprocess:
            for keyword in node.keywords:
                if keyword.arg == "shell":
                    if isinstance(keyword.value, ast.Constant):
                        if keyword.value.value is True:
                            violations.append(
                                f"line {node.lineno}: subprocess.{func.attr}(shell=True)"
                            )

    return violations


def _check_string_eval_patterns(filepath: Path) -> list[str]:
    """Check for string-based eval patterns like eval(f'...') or eval(input()).

    These are more dangerous than eval of known strings because the input
    is dynamic.
    """
    violations = []
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return violations

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        is_eval_exec = False
        call_name = None

        if isinstance(func, ast.Name) and func.id in ("eval", "exec"):
            is_eval_exec = True
            call_name = func.id

        if is_eval_exec and not _is_allowlisted(filepath, call_name):
            # Check if the first argument is a JoinedStr (f-string) or a Call
            if node.args:
                arg = node.args[0]
                if isinstance(arg, ast.JoinedStr):
                    violations.append(
                        f"line {node.lineno}: {call_name}(f'...') — eval of f-string"
                    )
                elif isinstance(arg, ast.Call):
                    # eval(input()), eval(some_function())
                    if isinstance(arg.func, ast.Name) and arg.func.id == "input":
                        violations.append(
                            f"line {node.lineno}: {call_name}(input()) — eval of user input"
                        )

    return violations


class CodeSafetyBoundaryTests(unittest.TestCase):
    """Ensure harness code does not use dangerous patterns."""

    def test_no_eval_or_exec_calls(self):
        """eval() and exec() are forbidden in harness code."""
        all_violations = []
        for filepath in _iter_python_files():
            violations = _check_dangerous_calls(filepath)
            for v in violations:
                rel = filepath.relative_to(ROOT)
                all_violations.append(f"{rel}: {v}")

        self.assertEqual(
            all_violations,
            [],
            f"Found dangerous eval/exec/os.system calls:\n"
            + "\n".join(all_violations),
        )

    def test_no_shell_true_in_subprocess(self):
        """subprocess calls must not use shell=True."""
        all_violations = []
        for filepath in _iter_python_files():
            violations = _check_shell_true(filepath)
            for v in violations:
                rel = filepath.relative_to(ROOT)
                all_violations.append(f"{rel}: {v}")

        self.assertEqual(
            all_violations,
            [],
            f"Found subprocess with shell=True:\n"
            + "\n".join(all_violations),
        )

    def test_no_eval_of_dynamic_strings(self):
        """eval(f'...') and eval(input()) are forbidden."""
        all_violations = []
        for filepath in _iter_python_files():
            violations = _check_string_eval_patterns(filepath)
            for v in violations:
                rel = filepath.relative_to(ROOT)
                all_violations.append(f"{rel}: {v}")

        self.assertEqual(
            all_violations,
            [],
            f"Found eval of dynamic strings:\n"
            + "\n".join(all_violations),
        )

    def test_allowlist_is_minimal_and_documented(self):
        """Every allowlisted entry must have a documented reason."""
        for entry in ALLOWLIST:
            self.assertEqual(
                len(entry), 3,
                f"Allowlist entry must be (path, pattern, reason): {entry}"
            )
            path, pattern, reason = entry
            self.assertTrue(
                (ROOT / path).exists(),
                f"Allowlisted file does not exist: {path}"
            )
            self.assertIn(
                pattern,
                ("eval", "exec", "os.system", "os.popen"),
                f"Unknown pattern in allowlist: {pattern}"
            )
            self.assertGreater(
                len(reason), 20,
                f"Allowlist reason too short (must document why): {reason}"
            )

    def test_allowlist_entries_are_actually_present(self):
        """Verify allowlisted files actually contain the flagged pattern."""
        for path, pattern, reason in ALLOWLIST:
            filepath = ROOT / path
            source = filepath.read_text(encoding="utf-8")
            if pattern == "eval":
                self.assertIn(
                    "eval(", source,
                    f"Allowlisted file {path} does not contain eval()"
                )
            elif pattern == "exec":
                self.assertIn(
                    "exec(", source,
                    f"Allowlisted file {path} does not contain exec()"
                )


if __name__ == "__main__":
    unittest.main()
