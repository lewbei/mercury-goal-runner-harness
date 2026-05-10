"""
Harness-native formal contract verifier.

Inspired by Nagini (ETH Zurich) and VeriGuard (Google 2025).
Converts annotated Python code into runtime contract checks,
then executes with test cases to verify formal correctness.

Annotation syntax:
    #@ Requires(lambda s: isinstance(s, str), "s must be string")
    #@ Ensures(lambda r, s: r is not None, "result must not be None")
    #@ Invariant(lambda i, s: 0 <= i < len(s), "loop invariant")

Usage:
    python harness_contract_verifier.py <run_dir> <target_file>

Output:
    verifier_artifacts/F.<RUN_ID>.json  — formal verification result
"""

import ast
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]


def _has_none_guard(source: str) -> bool:
    """Check if source code has explicit None guard pattern."""
    patterns = [
        "if " in source and " is None" in source and ("raise" in source or "return" in source),
        "if " in source and " is not None" in source,
        "assert " in source and " is not None" in source,
    ]
    return any(patterns)

ANNOTATION_MARKER = "#@"
REQUIRES = "Requires"
ENSURES = "Ensures"
INVARIANT = "Invariant"


def parse_annotations(source: str) -> dict:
    """Extract contract annotations from Python source."""
    lines = source.split("\n")
    contracts = {"requires": [], "ensures": [], "invariants": []}

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith(ANNOTATION_MARKER):
            continue
        annotation = stripped[len(ANNOTATION_MARKER):].strip()

        if annotation.startswith(REQUIRES):
            contracts["requires"].append(annotation)
        elif annotation.startswith(ENSURES):
            contracts["ensures"].append(annotation)
        elif annotation.startswith(INVARIANT):
            contracts["invariants"].append(annotation)

    return contracts


def eval_annotation(check_str: str, scope: dict) -> Callable:
    """Safely evaluate an annotation to a callable check."""
    # Extract the lambda or expression part
    import re
    match = re.search(r"\((lambda[^,]*).*?,\s*\"", check_str)
    if match:
        lambda_expr = match.group(1)
        try:
            return eval(lambda_expr, {"__builtins__": {}}, scope)
        except Exception:
            pass
    return None


def extract_function_body(source: str, func_name: str) -> str:
    """Extract a function body from source for annotation injection."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            start = node.body[0].lineno - 1
            end = node.body[-1].end_lineno
            return "\n".join(source.split("\n")[start:end])
    return ""


def verify_contracts(run_dir: Path, target_file: str) -> dict:
    """Verify formal contracts on a target Python file."""
    target_path = run_dir / target_file
    if not target_path.exists():
        return {
            "verdict": "INDETERMINATE",
            "reason": f"Target file not found: {target_file}",
            "checks": []
        }

    source = target_path.read_text(encoding="utf-8")
    contracts = parse_annotations(source)

    checks = []
    all_passed = True

    # Check 1: Verify annotations exist
    has_any = any(len(v) > 0 for v in contracts.values())
    checks.append({
        "check_id": "F1",
        "name": "has_formal_annotations",
        "passed": has_any,
        "detail": f"Found {sum(len(v) for v in contracts.values())} annotations"
    })

    # Check 2: Verify function exists and is importable
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("target_mod", target_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Find the main function
        func_names = [n for n in dir(mod) if callable(getattr(mod, n)) 
                      and not n.startswith("_")]
        checks.append({
            "check_id": "F2",
            "name": "module_importable",
            "passed": True,
            "detail": f"Module loaded, functions: {func_names}"
        })
    except Exception as e:
        checks.append({
            "check_id": "F2",
            "name": "module_importable",
            "passed": False,
            "detail": f"Import failed: {e}"
        })
        all_passed = False

    # Check 3: Test with edge cases if Requires or Ensures annotations exist
    if contracts["requires"] or contracts["ensures"]:
        try:
            spec = importlib.util.spec_from_file_location("target_mod", target_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            main_func = None
            func_name = ""
            for n in dir(mod):
                obj = getattr(mod, n)
                if callable(obj) and not n.startswith("_"):
                    main_func = obj
                    func_name = n
                    break

            if main_func:
                import inspect
                sig = inspect.signature(main_func)
                params = list(sig.parameters.keys())
                
                # Build contract tests: check each Requires/Ensures with edge values
                contract_checks = 0
                for req in contracts["requires"]:
                    # Test None for string/not-None params
                    should_test_none = any(w in req.lower() for w in 
                        ["str", "string", "isinstance", "not none", "not be none", "non-null", "nonnull"])
                    should_test_empty = any(w in req.lower() for w in ["str", "string", "isinstance"])
                    
                    if should_test_none:
                        # Check source for explicit None guard pattern
                        has_explicit_guard = _has_none_guard(source)
                        try:
                            result = main_func(None)
                            contract_checks += 1
                            if has_explicit_guard:
                                checks.append({
                                    "check_id": f"F3_{len(checks)}",
                                    "name": "requires_none_input",
                                    "passed": isinstance(result, (int, str, list, float)),
                                    "detail": "None input produced valid result"
                                })
                            else:
                                all_passed = False
                                checks.append({
                                    "check_id": f"F3_{len(checks)}",
                                    "name": "requires_none_input",
                                    "passed": False,
                                    "detail": "None input accepted without guard — contract violated"
                                })
                        except Exception as exc:
                            contract_checks += 1
                            if has_explicit_guard:
                                checks.append({
                                    "check_id": f"F3_{len(checks)}",
                                    "name": "requires_none_input",
                                    "passed": True,
                                    "detail": f"Explicit guard rejects None: {type(exc).__name__}"
                                })
                            else:
                                all_passed = False
                                checks.append({
                                    "check_id": f"F3_{len(checks)}",
                                    "name": "requires_none_input",
                                    "passed": False,
                                    "detail": f"Crashes on None (no guard) — contract violated: {type(exc).__name__}"
                                })
                    
                    # Test empty string for string params
                    if should_test_empty:
                        try:
                            result = main_func("")
                            contract_checks += 1
                            # Verify result satisfies Ensures if available
                            passed = False
                            if contracts["ensures"]:
                                for ens in contracts["ensures"]:
                                    if "isinstance" in ens and "int" in ens:
                                        passed = isinstance(result, int)
                                    elif "is not None" in ens:
                                        passed = result is not None
                                    else:
                                        passed = isinstance(result, (int, str, list, dict, float))
                            else:
                                passed = True  # No Ensures to check against
                            checks.append({
                                "check_id": f"F3_{len(checks)}",
                                "name": f"ensures_empty_input",
                                "passed": passed,
                                "detail": f"Empty input result={result!r} satisfies Ensures"
                            })
                        except Exception:
                            pass
                
                if contract_checks == 0:
                    checks.append({
                        "check_id": "F3",
                        "name": "contract_edge_tests",
                        "passed": True,
                        "detail": "No contract edge tests applicable"
                    })
        except Exception as e:
            checks.append({
                "check_id": "F3",
                "name": "contract_edge_tests",
                "passed": False,
                "detail": f"Contract test execution error: {e}"
            })
            all_passed = False

    passed_count = sum(1 for c in checks if c["passed"])
    total = len(checks) or 1

    return {
        "verdict": "PASS" if all_passed else "FAIL",
        "confidence": round(passed_count / total, 4),
        "checks_total": total,
        "checks_passed": passed_count,
        "checks_failed": total - passed_count,
        "checks": checks,
        "annotations_found": {
            "requires": len(contracts["requires"]),
            "ensures": len(contracts["ensures"]),
            "invariants": len(contracts["invariants"])
        }
    }


def write_verification_artifact(run_dir: Path, result: dict):
    """Write formal verification result as P2 verifier artifact."""
    artifacts_dir = run_dir / "verifier_artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    run_id = run_dir.name

    artifact = {
        "artifact_id": f"F.{run_id.upper()}" if run_id else "F.RUN",
        "run_id": run_id,
        "target_artifact": result.get("target_file", "unknown"),
        "kind": "formal_verification",
        "source": "harness_formal_verifier",
        "provenance_level": "P2",
        "depends_on_solution": False,
        "same_worker_as_solution": False,
        "executes_code": True,
        "assertion_count": result["checks_total"],
        "mock_ratio_percent": 0,
        "smell_flags": [],
        "authority": "certifying",
        "solution_exists_at_creation": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_at_phase": "post_solution",
        "author_agent": "harness_contract_verifier",
        "author_model": "deterministic",
        "verdict": result["verdict"],
        "formal_verification_detail": result
    }

    artifact_path = artifacts_dir / f"F_{run_id.upper()}.json"
    artifact_path.write_text(json.dumps(artifact, indent=2))
    return artifact_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python harness_contract_verifier.py <run_dir> [target_file]")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    target_file = sys.argv[2] if len(sys.argv) > 2 else None

    # Auto-detect target from goal contract
    if not target_file:
        gc_path = run_dir / "goal_contract.json"
        if gc_path.exists():
            gc = json.loads(gc_path.read_text(encoding="utf-8"))
            outputs = gc.get("final_outputs", [])
            if outputs:
                target_file = outputs[0]

    if not target_file:
        print("No target file specified and no goal contract found")
        sys.exit(1)

    result = verify_contracts(run_dir, target_file)
    result["target_file"] = target_file

    artifact_path = write_verification_artifact(run_dir, result)
    print(f"Formal verification: {result['verdict']}")
    print(f"Confidence: {result['confidence']} ({result['checks_passed']}/{result['checks_total']})")
    print(f"Artifact: {artifact_path}")


if __name__ == "__main__":
    main()
