#!/usr/bin/env python3
"""Strict verification pipeline — runs deterministic framework layers.

Usage:
  python .agentic-pi/runtime/full_verify.py .agentic-runs/<run_id>

This strict path never synthesizes missing proof artifacts. Planning search,
planning coverage, plan artifacts, expected_artifacts.json,
verifier_contract.json, and verifier_artifacts/ must already exist before this
runner starts. If adaptive_research_inputs.json exists, it is validated as an
optional planning-only input. Missing prerequisites produce NOT_DONE instead of
fabricated contracts or generated compatibility plans.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".agentic-pi" / "runtime"
VALIDATORS = ROOT / ".agentic-pi" / "validators"


def run_tool(tool_path: str, args: list[str], label: str) -> bool:
    print(f"  [{label}] ", end="", flush=True)
    try:
        result = subprocess.run(
            [sys.executable, tool_path, *args],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=30
        )
        if result.returncode == 0:
            print("PASS")
            return True
        else:
            print(f"FAIL (exit {result.returncode})")
            for line in (result.stdout or "").splitlines()[:2]:
                print(f"    {line}")
            return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def verify(run_dir: Path, *, skip_memory_consolidation: bool = False) -> str:
    run_id = run_dir.name
    print(f"\n{'='*60}")
    print(f"FULL VERIFICATION: {run_id}")
    print(f"{'='*60}")

    # Layer 0: Plan artifacts + verifier contract
    print("\n[Layer 0] Required proof artifacts")
    if not _require_preexisting_proof_artifacts(run_dir):
        return "NOT_DONE"

    deterministic_layers_ok = True

    # Layer 0A: Planning search/coverage gates. These are not certifiers, but
    # full verification requires valid planning evidence before policy/certifier
    # status can be considered.
    print("\n[Layer 0A] Planning search and coverage gates")
    if (run_dir / "adaptive_research_inputs.json").is_file():
        deterministic_layers_ok &= run_tool(f"{VALIDATORS}/validate_adaptive_research_inputs.py", [str(run_dir)], "validate_adaptive_research_inputs")
    else:
        print("  [validate_adaptive_research_inputs] SKIP (optional planning input absent)")
    deterministic_layers_ok &= run_tool(f"{VALIDATORS}/validate_planning_search_tree.py", [str(run_dir)], "validate_planning_search_tree")
    deterministic_layers_ok &= run_tool(f"{VALIDATORS}/validate_planning_coverage.py", [str(run_dir)], "validate_planning_coverage")

    # Layer 0B: Planning quality gate (optional, advisory)
    # The v1.1 quality gate includes skeptic/attack review. Its absence is a
    # warning, not a blocker — the certifier still runs regardless.
    print("\n[Layer 0B] Planning quality gate (advisory)")
    quality_report = run_dir / "planning_coordination_v1_1_quality_report.json"
    if quality_report.is_file():
        try:
            qr = json.loads(quality_report.read_text(encoding="utf-8"))
            if qr.get("quality_gate_passed"):
                print("  [planning_quality] PASS — skeptic/attack review completed")
            else:
                print("  [planning_quality] WARNING — quality gate did not pass")
        except Exception as exc:
            print(f"  [planning_quality] WARNING — could not read report: {exc}")
    else:
        print("  [planning_quality] SKIP — v1.1 quality report absent (skeptic review not verified)")

    # Layer 1: Artifact routing
    print("\n[Layer 1] Artifact routing")
    deterministic_layers_ok &= run_tool(f"{RUNTIME}/artifact_linker.py", [run_id], "artifact_linker")
    deterministic_layers_ok &= run_tool(f"{RUNTIME}/task_graph_builder.py", [run_id], "task_graph_builder")

    # Layer 2: Verifier provenance
    print("\n[Layer 2] Verifier provenance")
    deterministic_layers_ok &= run_tool(f"{VALIDATORS}/smell_scanner.py", [str(run_dir)], "smell_scanner")
    deterministic_layers_ok &= run_tool(f"{VALIDATORS}/strength_scorer.py", [str(run_dir)], "strength_scorer")

    # Layer 3: Policy engine
    print("\n[Layer 3] Policy engine")
    deterministic_layers_ok &= run_tool(f"{RUNTIME}/policy_engine.py", [str(run_dir)], "policy_engine")

    # Layer 4: Evidence indexing
    print("\n[Layer 4] Evidence indexing")
    deterministic_layers_ok &= run_tool(f"{RUNTIME}/evidence_freezer.py", [str(run_dir)], "evidence_freezer")
    deterministic_layers_ok &= run_tool(f"{RUNTIME}/evidence_indexer.py", [str(run_dir)], "evidence_indexer")

    # Layer 5: Replay
    print("\n[Layer 5] Replay certification")
    deterministic_layers_ok &= run_tool(f"{RUNTIME}/replay_run.py", [str(run_dir)], "replay")
    _ensure_replay_verdict(run_dir)

    if not deterministic_layers_ok:
        print("  STRICT_LAYER_FAILED: deterministic verification layer failed before certifier")
        return "DONE_FAIL"

    # Layer 6: Certifier
    print("\n[Layer 6] Certifier")
    result = subprocess.run(
        [sys.executable, f"{VALIDATORS}/certify_run.py", str(run_dir)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    output = result.stdout or ""
    print(output[:300] if len(output) > 300 else output)

    # Layer 7: Memory (advisory only; never certifies)
    print("\n[Layer 7] Memory consolidation")
    if skip_memory_consolidation:
        print("  skipped by caller; certifier-owned status is unchanged")
    elif not _run_memory_consolidation(run_dir, run_id):
        print("  memory consolidation incomplete; certifier-owned status is unchanged")

    # Read final status
    cert_path = run_dir / "certification.json"
    if cert_path.exists():
        cert = json.loads(cert_path.read_text(encoding="utf-8"))
        return cert.get("status", "DONE_FAIL")
    return "DONE_FAIL"


def _require_preexisting_proof_artifacts(run_dir: Path) -> bool:
    """Return True only when strict proof prerequisites already exist.

    This function is intentionally read-only. It reports missing prerequisites
    but never creates plan graphs, merged plans, selected plans, verifier
    contracts, or verifier artifacts.
    """
    required_files = [
        "goal_contract.json",
        "planning_search_tree.json",
        "planning_coverage.json",
        "plan_graph.json",
        "merged_plan.json",
        "selected_plan.json",
        "expected_artifacts.json",
        "verifier_contract.json",
    ]
    missing = [name for name in required_files if not (run_dir / name).is_file()]

    verifier_dir = run_dir / "verifier_artifacts"
    verifier_artifacts = sorted(verifier_dir.glob("*.json")) if verifier_dir.is_dir() else []
    if not verifier_artifacts:
        missing.append("verifier_artifacts/*.json")

    if missing:
        print("  STRICT_PRECHECK_FAILED")
        for item in missing:
            print(f"    missing required proof artifact: {item}")
        print("  full_verify.py did not create generated compatibility proof artifacts")
        return False

    print("  required proof artifacts exist")
    return True


def _ensure_replay_verdict(run_dir: Path):
    rp = run_dir / "replay_report.json"
    if not rp.exists():
        return
    try:
        data = json.loads(rp.read_text(encoding="utf-8"))
        if "verdict" not in data:
            has_mismatch = any(not c.get("passed", True) for c in data.get("checks", {}).values() if isinstance(c, dict))
            data["verdict"] = "REPLAY_MISMATCH" if has_mismatch else "REPLAY_MATCH"
            rp.write_text(json.dumps(data, indent=2))
    except Exception as exc:
        print(f"  replay verdict normalization skipped: {exc}")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _memory_destination(outcome_kind: str) -> tuple[str, str, str]:
    if outcome_kind == "success":
        return "planning", "plan_seed_patterns", "run_lessons"
    if outcome_kind == "provisional":
        return "verification", "weak_oracle_patterns", "run_lessons"
    if outcome_kind == "failure":
        return "verification", "false_done_cases", "run_lessons"
    return "anti_overclaim", "agent_report_not_certification", "run_lessons"


def _build_memory_card(run_dir: Path, run_id: str, experience: dict) -> dict | None:
    principle = str(experience.get("principle") or "").strip()
    evidence_refs = [str(ref) for ref in experience.get("evidence_files", []) if str(ref).strip()]
    if not principle or not evidence_refs:
        return None

    outcome_kind = str(experience.get("outcome_kind") or "unknown")
    wing, room, drawer = _memory_destination(outcome_kind)
    return {
        "schema_version": "mempalace_ace_card_v1",
        "card_id": f"{run_id}-{outcome_kind}-lesson",
        "wing": wing,
        "room": room,
        "drawer": drawer,
        "type": "run_lesson",
        "content": principle,
        "source_run_id": run_id,
        "source_phase": "post_certification_memory",
        "evidence_refs": evidence_refs,
        "helpful_count": 1 if outcome_kind == "success" else 0,
        "harmful_count": 1 if outcome_kind == "failure" else 0,
        "card_status": "candidate",
        "authority_level": "advisory_only",
        "can_certify_done": False,
        "do_not_use_when": [str(item) for item in experience.get("do_not_use_when", [])],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _run_memory_consolidation(run_dir: Path, run_id: str) -> bool:
    """Run real advisory-memory gates without changing certifier status."""
    ok = True
    ok &= run_tool(f"{RUNTIME}/experience_extractor.py", [str(run_dir)], "experience_extractor")
    experience_path = run_dir / "experience_extract.json"
    if not experience_path.is_file():
        print("  memory: skipped promotion because experience_extract.json is missing")
        return False

    try:
        experience = load_json(experience_path)
    except Exception as exc:
        print(f"  memory: experience_extract.json unreadable: {exc}")
        return False

    principle = str(experience.get("principle") or "").strip()
    evidence_refs = [str(ref) for ref in experience.get("evidence_files", []) if str(ref).strip()]
    details = json.dumps({
        "outcome_kind": experience.get("outcome_kind", "unknown"),
        "evidence_refs": evidence_refs,
    }, ensure_ascii=False)

    ok &= run_tool(
        f"{RUNTIME}/run_memory_clerk.py",
        [str(run_dir), "--phase", "memory_effect", "--message", principle or "Experience extraction produced no principle", "--target-file", "experience_extract.json", "--details", details],
        "run_memory_clerk",
    )
    if principle:
        ok &= run_tool(
            f"{RUNTIME}/quarantine_memory_writer.py",
            [str(run_dir), "--source-run-id", run_id, "--principle", principle, "--evidence-refs", ",".join(evidence_refs)],
            "quarantine_memory_writer",
        )

    ok &= run_tool(f"{VALIDATORS}/validate_run_local_memory.py", [str(run_dir)], "validate_run_local_memory")
    ok &= run_tool(f"{VALIDATORS}/validate_quarantine_memory.py", [str(run_dir)], "validate_quarantine_memory")

    card = _build_memory_card(run_dir, run_id, experience)
    if card is None:
        print("  memory: skipped durable promotion because principle or evidence_refs are missing")
        return ok

    card_path = run_dir / "mempalace_card.json"
    decision_path = run_dir / "memory_write_decision.json"
    write_json(card_path, card)
    ok &= run_tool(f"{VALIDATORS}/validate_memory_card.py", [str(card_path)], "validate_memory_card")
    ok &= run_tool(
        f"{RUNTIME}/memory_write_gate.py",
        [str(run_dir), "--card", str(card_path), "--decision-output", str(decision_path)],
        "memory_write_gate",
    )
    if decision_path.is_file():
        ok &= run_tool(f"{VALIDATORS}/validate_memory_write_gate.py", [str(decision_path)], "validate_memory_write_gate")
    else:
        print("  memory: memory_write_decision.json missing")
        ok = False
    return ok


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Strict verification pipeline for prepared run folders")
    parser.add_argument("run_dir", help=".agentic-runs/<run_id> folder")
    parser.add_argument(
        "--skip-memory-consolidation",
        action="store_true",
        help="Skip advisory memory consolidation; certifier-owned status is unchanged",
    )
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    status = verify(run_dir, skip_memory_consolidation=args.skip_memory_consolidation)
    print(f"\nFINAL: {status}")
    sys.exit(0 if status in ("DONE_PASS", "CERTIFIED_DONE", "PROVISIONAL_DONE") else 1)
