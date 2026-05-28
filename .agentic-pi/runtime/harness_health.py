"""Harness health check — visibility into what's tested, what's missing.

Reports:
  Module coverage    — which .agentic-pi modules have test references
  Critical path gaps — untested modules on the hot path
  Dead code          — functions defined but never referenced
  Gate coverage      — which certifier gates have regression tests
  Doc freshness      — which docs reference missing files

Usage:
  python .agentic-pi/runtime/harness_health.py
  python .agentic-pi/runtime/harness_health.py --json
  python .agentic-pi/runtime/harness_health.py --critical-only
"""
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTIC_PI = ROOT / ".agentic-pi"
TESTS = ROOT / "tests"
DOCS = ROOT / "docs"

# Critical path modules — these are called by run_goal.py, full_verify.py,
# or certify_run.py. If they break, the pipeline breaks.
CRITICAL_PATH = {
    "runtime/init_run.py",
    "runtime/roadmap_planner.py",
    "runtime/guarded_worker.py",
    "runtime/artifact_linker.py",
    "runtime/task_graph_builder.py",
    "runtime/plan_router.py",
    "runtime/plan_selector.py",
    "runtime/plan_merger.py",
    "runtime/plan_graph_builder.py",
    "runtime/full_verify.py",
    "runtime/policy_engine.py",
    "runtime/gateway_dispatch.py",
    "runtime/command_gateway.py",
    "runtime/orchestrate_pipeline.py",
    "runtime/run_goal.py",
    "runtime/pi_cli.py",
    "runtime/check_matrix.py",
    "runtime/build_repair_prompt.py",
    "runtime/adversarial_loop.py",
    "runtime/replay_run.py",
    "runtime/audit_run.py",
    "runtime/evidence_freezer.py",
    "runtime/evidence_indexer.py",
    "runtime/update_memory_from_runs.py",
    "runtime/run_subagent_memory.py",
    "runtime/memory_write_gate.py",
    "runtime/prompt_provenance.py",
    "runtime/trace_logger.py",
    "runtime/context_builder.py",
    "runtime/context_engineer.py",
    "runtime/context_injector.py",
    "runtime/stage3_runtime_preflight.py",
    "runtime/planning_coordination_v1.py",
    "runtime/planning_coordination_v1_1_quality.py",
    "runtime/guarded_execution_v2.py",
    "validators/certify_run.py",
    "validators/certifier_gates.py",
    "validators/certifier_io.py",
    "validators/certifier_paths.py",
    "validators/certifier_artifact_commands.py",
    "validators/smell_scanner.py",
    "validators/strength_scorer.py",
    "validators/validate_schema.py",
    "validators/validate_goal_contract.py",
    "validators/validate_plan_graph.py",
    "validators/validate_final_status.py",
    "validators/validate_certification.py",
    "validators/validate_policy_decision.py",
    "validators/validate_memory_authority.py",
    "validators/validate_memory_write_gate.py",
    "formal/harness_contract_verifier.py",
    "formal/harness_signing.py",
}

# Certifier gates that should have regression tests
CERTIFIER_GATES = [
    "apply_formal_verification_gate",
    "apply_cryptographic_signature_gate",
    "apply_artifact_location_gate",
    "apply_audit_report_gate",
    "apply_replay_gate",
    "apply_drift_report_gate",
    "apply_evidence_freeze_gate",
    "apply_memory_authority_gate",
    "evaluate_done_criteria",
    "check_validator_certification",
]


def _iter_source_files():
    """Yield all .py files under .agentic-pi/, skipping __pycache__."""
    for path in AGENTIC_PI.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if path.name == "__init__.py":
            continue
        yield path


def _iter_test_files():
    """Yield all test_*.py files under tests/."""
    for path in TESTS.glob("test_*.py"):
        yield path


def _module_relpath(path: Path) -> str:
    """Return relative path from .agentic-pi/."""
    return str(path.relative_to(AGENTIC_PI)).replace("\\", "/")


def _has_test_reference(module_name: str, test_files: list[Path]) -> bool:
    """Check if any test file references this module name."""
    for tf in test_files:
        try:
            content = tf.read_text(encoding="utf-8")
            if module_name in content:
                return True
        except Exception:
            pass
    return False


def check_module_coverage():
    """Report which modules have test references and which don't."""
    test_files = list(_iter_test_files())
    covered = []
    uncovered = []

    for src in _iter_source_files():
        module_name = src.stem
        rel = _module_relpath(src)
        if _has_test_reference(module_name, test_files):
            covered.append(rel)
        else:
            uncovered.append(rel)

    return {
        "total_modules": len(covered) + len(uncovered),
        "covered": len(covered),
        "uncovered": len(uncovered),
        "coverage_pct": round(len(covered) / max(1, len(covered) + len(uncovered)) * 100, 1),
        "uncovered_list": sorted(uncovered),
    }


def check_critical_path_gaps():
    """Report which critical path modules have no test reference."""
    test_files = list(_iter_test_files())
    gaps = []

    for rel in sorted(CRITICAL_PATH):
        module_path = AGENTIC_PI / rel
        if not module_path.exists():
            gaps.append({"module": rel, "status": "MISSING"})
            continue
        module_name = module_path.stem
        if not _has_test_reference(module_name, test_files):
            gaps.append({"module": rel, "status": "NO_TEST"})

    return {
        "critical_modules": len(CRITICAL_PATH),
        "gaps": len(gaps),
        "gap_list": gaps,
    }


def check_dead_code():
    """Find functions defined in .agentic-pi/ but never referenced anywhere.

    A function is considered "possibly dead" only if:
    1. It is not referenced in any OTHER file, AND
    2. It is not called within its OWN file (only defined, never used)
    """
    # Collect all function definitions
    all_funcs = {}  # name -> [file1, file2, ...]
    for src in _iter_source_files():
        try:
            source = src.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if not node.name.startswith("_"):
                        rel = _module_relpath(src)
                        all_funcs.setdefault(node.name, []).append(rel)
        except (SyntaxError, UnicodeDecodeError):
            pass

    # Collect all source content for cross-reference
    all_source_content = {}
    for src in _iter_source_files():
        try:
            all_source_content[_module_relpath(src)] = src.read_text(encoding="utf-8")
        except Exception:
            pass

    # Also collect test file content
    test_content = ""
    for tf in _iter_test_files():
        try:
            test_content += tf.read_text(encoding="utf-8")
        except Exception:
            pass

    # Check which functions are referenced nowhere
    dead = []
    for func_name, source_files in all_funcs.items():
        # Check if referenced in any other source file
        referenced_elsewhere = False
        for rel, content in all_source_content.items():
            if rel in source_files:
                continue  # Skip the defining file
            if func_name in content:
                referenced_elsewhere = True
                break

        # Check if referenced in test files
        referenced_in_tests = func_name in test_content

        # Check if called within its own file (not just defined)
        referenced_locally = False
        for rel in source_files:
            content = all_source_content.get(rel, "")
            # Count occurrences - if > 1, it's used (defined + called)
            if content.count(func_name) > 1:
                referenced_locally = True
                break

        # Only flag as dead if not referenced anywhere
        if not referenced_elsewhere and not referenced_locally and not referenced_in_tests:
            dead.append({"function": func_name, "defined_in": source_files})

    return {
        "total_public_functions": len(all_funcs),
        "possibly_dead": len(dead),
        "dead_list": sorted(dead, key=lambda x: x["function"])[:30],  # Top 30
    }


def check_gate_coverage():
    """Report which certifier gates have regression tests."""
    test_files = list(_iter_test_files())
    results = []

    for gate in CERTIFIER_GATES:
        has_test = False
        test_file = None
        for tf in test_files:
            try:
                content = tf.read_text(encoding="utf-8")
                if gate in content:
                    has_test = True
                    test_file = tf.name
                    break
            except Exception:
                pass
        results.append({
            "gate": gate,
            "has_test": has_test,
            "test_file": test_file,
        })

    tested = sum(1 for r in results if r["has_test"])
    return {
        "total_gates": len(CERTIFIER_GATES),
        "tested": tested,
        "untested": len(CERTIFIER_GATES) - tested,
        "details": results,
    }


def check_doc_freshness():
    """Check which docs reference files that don't exist.

    References in sections marked [PLANNED] are skipped.
    """
    issues = []
    if not DOCS.exists():
        return {"issues": [], "total_checked": 0}

    doc_files = list(DOCS.glob("*.md"))
    for doc in doc_files:
        try:
            content = doc.read_text(encoding="utf-8")
        except Exception:
            continue

        doc_lines = content.splitlines()

        # Track which lines are in a [PLANNED] section
        planned_lines = set()
        in_planned = False
        for i, line in enumerate(doc_lines):
            if "[PLANNED" in line.upper():
                in_planned = True
            elif line.startswith("###") or line.startswith("## "):
                in_planned = False
            if in_planned:
                planned_lines.add(i)

        import re
        for i, line in enumerate(doc_lines):
            refs = re.findall(r'\.agentic-pi/[^\s`"\']+\.py', line)
            for ref in refs:
                ref_clean = ref.rstrip("`\"',;:)")
                full_path = ROOT / ref_clean
                if not full_path.exists():
                    if i in planned_lines:
                        continue
                    issues.append({
                        "doc": doc.name,
                        "references": ref_clean,
                        "status": "MISSING",
                    })

    return {
        "total_docs": len(doc_files),
        "issues": len(issues),
        "issue_list": sorted(issues, key=lambda x: x["doc"])[:20],
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Harness health check")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--critical-only", action="store_true", help="Show only critical path gaps")
    args = parser.parse_args()

    results = {
        "module_coverage": check_module_coverage(),
        "critical_path": check_critical_path_gaps(),
        "dead_code": check_dead_code(),
        "gate_coverage": check_gate_coverage(),
        "doc_freshness": check_doc_freshness(),
    }

    if args.json:
        print(json.dumps(results, indent=2))
        return

    # ── Module Coverage ──────────────────────────────────────────────────
    mc = results["module_coverage"]
    print("=" * 70)
    print("HARNESS HEALTH CHECK")
    print("=" * 70)
    print()

    if not args.critical_only:
        # ── Module Coverage ──────────────────────────────────────────────────
        mc = results["module_coverage"]
        print(f"MODULE COVERAGE")
        print(f"  Total modules:  {mc['total_modules']}")
        print(f"  With tests:     {mc['covered']} ({mc['coverage_pct']}%)")
        print(f"  Without tests:  {mc['uncovered']}")
        if mc["uncovered_list"]:
            print(f"  Gap list:")
            for m in mc["uncovered_list"][:15]:
                print(f"    - {m}")
            if len(mc["uncovered_list"]) > 15:
                print(f"    ... and {len(mc['uncovered_list']) - 15} more")
        print()

    # ── Critical Path ───────────────────────────────────────────────────
    cp = results["critical_path"]
    print()
    print(f"CRITICAL PATH GAPS")
    print(f"  Critical modules: {cp['critical_modules']}")
    print(f"  With gaps:        {cp['gaps']}")
    if cp["gap_list"]:
        print(f"  WARNING: These modules are on the hot path but have NO test coverage:")
        for g in cp["gap_list"]:
            marker = "X MISSING" if g["status"] == "MISSING" else "! NO TEST"
            print(f"    {marker}: {g['module']}")

    if args.critical_only:
        return

    # ── Dead Code ───────────────────────────────────────────────────────
    dc = results["dead_code"]
    print()
    print(f"DEAD CODE DETECTION")
    print(f"  Public functions:    {dc['total_public_functions']}")
    print(f"  Possibly dead:       {dc['possibly_dead']}")
    if dc["dead_list"]:
        print(f"  Top candidates:")
        for d in dc["dead_list"][:10]:
            print(f"    - {d['function']} ({', '.join(d['defined_in'])})")

    # ── Gate Coverage ───────────────────────────────────────────────────
    gc = results["gate_coverage"]
    print()
    print(f"CERTIFIER GATE COVERAGE")
    print(f"  Total gates:  {gc['total_gates']}")
    print(f"  Tested:       {gc['tested']}")
    print(f"  Untested:     {gc['untested']}")
    for g in gc["details"]:
        marker = "[OK]" if g["has_test"] else "[--]"
        test_info = f" ({g['test_file']})" if g["test_file"] else ""
        print(f"    {marker} {g['gate']}{test_info}")

    # ── Doc Freshness ───────────────────────────────────────────────────
    df = results["doc_freshness"]
    print()
    print(f"DOC FRESHNESS")
    print(f"  Docs checked:  {df['total_docs']}")
    print(f"  Issues:        {df['issues']}")
    if df["issue_list"]:
        print(f"  Stale references:")
        for i in df["issue_list"][:10]:
            print(f"    - {i['doc']} references {i['references']} (MISSING)")

    # ── Summary ─────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    total_issues = (
        mc["uncovered"]
        + cp["gaps"]
        + gc["untested"]
        + df["issues"]
    )
    if total_issues == 0:
        print("HEALTHY - no gaps detected")
    else:
        print(f"WARNING: {total_issues} issues detected")
        if cp["gaps"] > 0:
            print(f"   [HIGH] {cp['gaps']} critical path gaps (highest priority)")
        if gc["untested"] > 0:
            print(f"   [MED]  {gc['untested']} certifier gates without regression tests")
        if mc["uncovered"] > 0:
            print(f"   [LOW]  {mc['uncovered']} modules without test references")
        if df["issues"] > 0:
            print(f"   [LOW]  {df['issues']} stale doc references")
    print("=" * 70)


if __name__ == "__main__":
    main()
