"""Boundary scanner: detect illegal imports/paths to reference modules.

Reference modules (modules/ace-main, modules/mempalace-develop,
modules/nagini-develop) are reference material only.  Harness code under
.agentic-pi/ and tests/ must not import from them, manipulate sys.path
to reach them, or open/read files from them.

docs/ is excluded — it is allowed to reference these modules by design.
"""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Directories to scan (relative to ROOT)
SCAN_DIRS = [".agentic-pi", "tests"]

# Reference module identifiers
REFERENCE_MODULES = {"ace-main", "mempalace-develop", "nagini-develop"}
REFERENCE_MODULE_PATHS = {f"modules/{m}" for m in REFERENCE_MODULES}

# Patterns for string-level path references in open(), Path(), etc.
_PATH_PATTERN = re.compile(
    r"""(?:modules[/\\](?:ace-main|mempalace-develop|nagini-develop))""",
    re.IGNORECASE,
)

# Import targets that would pull from modules/*
_IMPORT_PATTERN = re.compile(
    r"""^(?:ace_main|mempalace_develop|nagini_develop|modules)$""",
)


# Files that legitimately reference module paths in assertions or docstrings.
_SELF = Path(__file__).resolve()
_KNOWN_BOUNDARY_TESTS = {
    # Tests that verify .gitignore/docs contain the expected reference paths
    _SELF.parent / "test_authority_evidence_memory_plan.py",
}

def _iter_python_files():
    """Yield all .py files under SCAN_DIRS, skipping __pycache__ and self."""
    for scan_dir in SCAN_DIRS:
        target = ROOT / scan_dir
        if not target.exists():
            continue
        for path in target.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            if path.resolve() == _SELF:
                continue
            if path.resolve() in {p.resolve() for p in _KNOWN_BOUNDARY_TESTS}:
                continue
            yield path


def _check_imports(filepath: Path) -> list[str]:
    """Return list of violations from import/from-import statements."""
    violations = []
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_module = alias.name.split(".")[0]
                if _IMPORT_PATTERN.match(root_module):
                    violations.append(
                        f"line {node.lineno}: import {alias.name}"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            # Check if 'from modules import ...' or 'from modules.X import ...'
            parts = node.module.split(".")
            if parts[0] == "modules":
                violations.append(
                    f"line {node.lineno}: from {node.module} import ..."
                )
            # Check if importing from ace_main / mempalace_develop / nagini_develop
            root_module = parts[0]
            if _IMPORT_PATTERN.match(root_module):
                violations.append(
                    f"line {node.lineno}: from {node.module} import ..."
                )
    return violations


def _check_path_references(filepath: Path) -> list[str]:
    """Return list of violations from string-level path references.

    Uses the AST to extract string literals, which automatically skips
    comments and is more reliable than line-by-line regex.
    """
    violations = []
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return violations

    # Collect (lineno, string_value) from AST string constants.
    # This covers docstrings, string assignments, f-strings (JoinedStr), etc.
    string_nodes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            string_nodes.append((node.lineno, node.value))
        elif isinstance(node, ast.JoinedStr):
            # f-strings: collect the constant parts
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    string_nodes.append((value.lineno, value.value))

    for lineno, value in string_nodes:
        # Skip assertion messages and .gitignore-related strings
        if "gitignore" in value.lower() or "ignored_paths" in value.lower():
            continue
        if "assertIn" in value or "assertNotIn" in value:
            continue

        if _PATH_PATTERN.search(value):
            violations.append(
                f"line {lineno}: string contains reference module path: {value[:120]}"
            )
    return violations


class ReferenceModuleBoundaryTests(unittest.TestCase):
    """Ensure harness code does not import from or reference reference modules."""

    def test_no_imports_from_reference_modules(self):
        """Imports from ace-main, mempalace-develop, nagini-develop are forbidden."""
        all_violations = []
        for filepath in _iter_python_files():
            violations = _check_imports(filepath)
            for v in violations:
                rel = filepath.relative_to(ROOT)
                all_violations.append(f"{rel}: {v}")

        self.assertEqual(
            all_violations,
            [],
            f"Found illegal imports from reference modules:\n"
            + "\n".join(all_violations),
        )

    def test_no_path_references_to_reference_modules(self):
        """String paths to modules/ace-main, etc. are forbidden outside docs/."""
        all_violations = []
        for filepath in _iter_python_files():
            violations = _check_path_references(filepath)
            for v in violations:
                rel = filepath.relative_to(ROOT)
                all_violations.append(f"{rel}: {v}")

        self.assertEqual(
            all_violations,
            [],
            f"Found illegal path references to reference modules:\n"
            + "\n".join(all_violations),
        )

    def test_reference_modules_not_in_python_path(self):
        """No sys.path manipulation targeting reference module directories."""
        all_violations = []
        for filepath in _iter_python_files():
            try:
                source = filepath.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for lineno, line in enumerate(source.splitlines(), start=1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "sys.path" in line and any(
                    m in line for m in REFERENCE_MODULES
                ):
                    rel = filepath.relative_to(ROOT)
                    all_violations.append(
                        f"{rel}:{lineno}: sys.path manipulation targeting reference module: {stripped}"
                    )

        self.assertEqual(
            all_violations,
            [],
            f"Found sys.path manipulation targeting reference modules:\n"
            + "\n".join(all_violations),
        )

    def test_reference_modules_not_copied_into_harness(self):
        """Verify no reference module content was vendored into .agentic-pi/."""
        harness_dir = ROOT / ".agentic-pi"
        if not harness_dir.exists():
            return

        vendored_indicators = []
        for module_name in REFERENCE_MODULES:
            # Check for directories named after reference modules inside .agentic-pi/
            for match in harness_dir.rglob(f"**/{module_name}/**"):
                if "__pycache__" not in match.parts:
                    vendored_indicators.append(
                        f"Found {match.relative_to(ROOT)} inside .agentic-pi/"
                    )
            # Check for files that match reference module naming patterns
            for match in harness_dir.rglob(f"*{module_name}*"):
                if match.is_file() and "__pycache__" not in match.parts:
                    vendored_indicators.append(
                        f"Found {match.relative_to(ROOT)} inside .agentic-pi/"
                    )

        self.assertEqual(
            vendored_indicators,
            [],
            f"Possible vendored reference module content:\n"
            + "\n".join(vendored_indicators),
        )


if __name__ == "__main__":
    unittest.main()
