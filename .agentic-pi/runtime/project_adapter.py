"""Project Adapter Layer

Scans a project directory and produces `project_map.json` describing files,
imports, entry points, and test files. Designed for integration with the
harness's artifact linker and task graph.
"""

import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any


def _is_git_repo(path: Path) -> bool:
    """Return True if *path* is inside a Git repository.

    Uses `git rev-parse --is-inside-work-tree`. Any non‑zero exit code
    indicates the directory is not a Git repo.
    """
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def _git_root(path: Path) -> Path:
    """Return the top‑level directory of the Git repository containing *path*.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip())


def _list_git_files(repo_root: Path) -> List[Path]:
    """List all tracked files in the repository using `git ls-files`.
    Returns absolute ``Path`` objects.
    """
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [repo_root / line for line in result.stdout.splitlines() if line]


def _list_all_files(root: Path) -> List[Path]:
    """Recursively walk *root* and return a list of all file paths.
    """
    return [p for p in root.rglob("*") if p.is_file()]


def _extract_imports(py_path: Path) -> List[str]:
    """Parse a Python file and return a list of top‑level imported module names.
    Handles `import X` and `from X import …` statements.
    """
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    except Exception as e:
        # If parsing fails, return an empty list but do not abort the whole scan.
        return []
    imports: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])
    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for name in imports:
        if name not in seen:
            seen.add(name)
            uniq.append(name)
    return uniq


def _is_entry_point(py_path: Path) -> bool:
    """Detect if a Python file contains a ``if __name__ == "__main__"`` guard.
    """
    try:
        text = py_path.read_text(encoding="utf-8")
    except Exception:
        return False
    return "if __name__ == \"__main__\"" in text


def _is_test_file(rel_path: str) -> bool:
    """Return True for files that look like tests.
    Heuristics:
    - filename starts with ``test_`` or ends with ``_test.py``
    - path contains a ``tests`` directory segment
    """
    parts = Path(rel_path).parts
    name = Path(rel_path).name
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return "tests" in parts


def generate_project_map(project_dir: str, output_path: str = "project_map.json") -> None:
    """Generate a JSON map of the project located at *project_dir*.

    The map is written to *output_path* (relative to the current working directory).
    """
    root = Path(project_dir).resolve()
    if not root.is_dir():
        raise RuntimeError(f"Project directory does not exist: {root}")

    # Determine file discovery strategy
    if _is_git_repo(root):
        repo_root = _git_root(root)
        files = _list_git_files(repo_root)
        # Convert to paths relative to the original *project_dir* for consistency
        rel_files = [f.relative_to(root) for f in files if f.is_file()]
    else:
        all_files = _list_all_files(root)
        rel_files = [f.relative_to(root) for f in all_files]

    file_entries: List[Dict[str, Any]] = []
    entry_points: List[str] = []
    test_files: List[str] = []
    dependencies: List[str] = []

    for rel_path in rel_files:
        abs_path = root / rel_path
        entry = {
            "path": str(rel_path),
            "type": "python" if rel_path.suffix == ".py" else "other",
            "imports": [],
            "is_entry_point": False,
            "is_test": False,
        }
        if rel_path.suffix == ".py":
            entry["imports"] = _extract_imports(abs_path)
            entry["is_entry_point"] = _is_entry_point(abs_path)
            entry["is_test"] = _is_test_file(str(rel_path))
            if entry["is_entry_point"]:
                entry_points.append(str(rel_path))
            if entry["is_test"]:
                test_files.append(str(rel_path))
        else:
            # Detect top‑level dependency descriptor files
            if rel_path.name in {"requirements.txt", "setup.py", "pyproject.toml"}:
                dependencies.append(str(rel_path))
        file_entries.append(entry)

    project_map = {
        "files": file_entries,
        "entry_points": entry_points,
        "test_files": test_files,
        "dependencies": dependencies,
    }

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(project_map, f, indent=2, ensure_ascii=False)
    except Exception as e:
        raise RuntimeError(f"Failed to write project map to {output_path}: {e}")


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Generate a project map for the harness.")
    parser.add_argument(
        "--project-dir",
        default=".",
        help="Path to the project directory (default: current directory)",
    )
    parser.add_argument(
        "--output",
        default="project_map.json",
        help="File to write the JSON map to (default: project_map.json)",
    )
    args = parser.parse_args()
    generate_project_map(args.project_dir, args.output)
    # Quick test output – must be at least two lines
    print(f"Generated {args.output}")
    try:
        with open(args.output, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"Files scanned: {len(data.get('files', []))}")
    except Exception:
        print("Failed to load generated map for summary.")

if __name__ == "__main__":
    _cli()
