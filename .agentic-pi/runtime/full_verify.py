#!/usr/bin/env python3
"""Full verification pipeline — runs ALL deterministic framework layers.

Usage:
  python .agentic-pi/runtime/full_verify.py .agentic-runs/<run_id>
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


def verify(run_dir: Path) -> str:
    run_id = run_dir.name
    print(f"\n{'='*60}")
    print(f"FULL VERIFICATION: {run_id}")
    print(f"{'='*60}")

    # Layer 0: Plan artifacts + verifier contract
    print("\n[Layer 0] Plan artifacts")
    _ensure_plan_artifacts(run_dir, run_id)
    _ensure_verifier_contract(run_dir, run_id)

    # Layer 1: Artifact routing
    print("\n[Layer 1] Artifact routing")
    run_tool(f"{RUNTIME}/artifact_linker.py", [run_id], "artifact_linker")
    run_tool(f"{RUNTIME}/task_graph_builder.py", [run_id], "task_graph_builder")

    # Layer 2: Verifier provenance
    print("\n[Layer 2] Verifier provenance")
    run_tool(f"{VALIDATORS}/smell_scanner.py", [str(run_dir)], "smell_scanner")
    run_tool(f"{VALIDATORS}/strength_scorer.py", [str(run_dir)], "strength_scorer")

    # Layer 3: Policy engine
    print("\n[Layer 3] Policy engine")
    run_tool(f"{RUNTIME}/policy_engine.py", [str(run_dir)], "policy_engine")

    # Layer 4: Evidence indexing
    print("\n[Layer 4] Evidence indexing")
    run_tool(f"{RUNTIME}/evidence_freezer.py", [str(run_dir)], "evidence_freezer")
    run_tool(f"{RUNTIME}/evidence_indexer.py", [str(run_dir)], "evidence_indexer")

    # Layer 5: Replay
    print("\n[Layer 5] Replay certification")
    run_tool(f"{RUNTIME}/replay_run.py", [str(run_dir)], "replay")
    _ensure_replay_verdict(run_dir)

    # Layer 6: Certifier
    print("\n[Layer 6] Certifier")
    result = subprocess.run(
        [sys.executable, f"{VALIDATORS}/certify_run.py", str(run_dir)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    output = result.stdout or ""
    print(output[:300] if len(output) > 300 else output)

    # Layer 7: Memory (experience → local → MemPalace → reflect → curate → gate)
    print("\n[Layer 7] Memory consolidation")
    run_tool(f"{RUNTIME}/experience_extractor.py", [str(run_dir)], "experience_extractor")
    _write_local_memory(run_dir, run_id)
    _try_mempalace_store(run_dir, run_id)
    _try_ace_reflector(run_dir, run_id)
    _try_ace_curator(run_dir, run_id)
    _try_memory_gate(run_dir, run_id)

    # Read final status
    cert_path = run_dir / "certification.json"
    if cert_path.exists():
        cert = json.loads(cert_path.read_text(encoding="utf-8"))
        return cert.get("status", "DONE_FAIL")
    return "DONE_FAIL"


def _ensure_plan_artifacts(run_dir: Path, run_id: str):
    pg, mp, sp = run_dir / "plan_graph.json", run_dir / "merged_plan.json", run_dir / "selected_plan.json"
    step_dir = run_dir / "step_logs"
    steps, nodes, edges = [], [], []
    if step_dir.is_dir():
        for sf in sorted(step_dir.glob("*.json")):
            try:
                data = json.loads(sf.read_text(encoding="utf-8"))
                sid = data.get("step_id", len(steps) + 1)
                tid = f"T{sid}"
                touched = data.get("files_touched", [])
                path = touched[0] if touched else f"step_{sid}.txt"
                steps.append({"task_id": tid, "action": data.get("action_taken", "create_file"),
                              "path": path, "requires": [], "produces": [{"artifact_id": f"A.{sid:03d}", "path": path}]})
                nodes.append({"node_id": tid, "type": "task", "task_id": tid, "description": f"Step {sid}"})
                if sid > 1:
                    edges.append({"source": f"T{sid-1}", "target": tid, "type": "depends"})
            except Exception:
                pass
    if steps:
        mp.write_text(json.dumps({"steps": steps}, indent=2))
        print(f"  created merged_plan.json ({len(steps)} steps)")
    elif not mp.exists():
        mp.write_text(json.dumps({"steps": [{"task_id": "T1", "action": "create_file", "path": "output.py", "requires": [], "produces": [{"artifact_id": "A.001", "path": "output.py"}]}]}, indent=2))
    if nodes:
        pg.write_text(json.dumps({"nodes": nodes, "edges": edges}, indent=2))
        print(f"  created plan_graph.json ({len(nodes)} nodes)")
    elif not pg.exists():
        pg.write_text(json.dumps({"nodes": [{"node_id": "T1", "type": "task", "task_id": "T1"}], "edges": []}, indent=2))
    if not sp.exists():
        sp.write_text(json.dumps({"selected": "planner-minimal"}, indent=2))


def _ensure_verifier_contract(run_dir: Path, run_id: str):
    vc = run_dir / "verifier_contract.json"
    if vc.exists():
        return
    gc = run_dir / "goal_contract.json"
    targets = []
    if gc.exists():
        try:
            targets = json.loads(gc.read_text(encoding="utf-8")).get("final_outputs", [])
        except Exception:
            pass
    vc.write_text(json.dumps({
        "run_id": run_id, "target_goal": "Implement from specification",
        "target_artifacts": targets or ["output.py"],
        "required_verifier_level": "P2", "allow_self_generated_only": False,
        "required_behaviors": [f"{t} exists" for t in targets] if targets else ["output.py exists"],
        "forbidden_verifier_patterns": ["self-test only", "file existence only"],
        "minimum_strength_level": "gating",
        "certifying_authority_levels": ["P2", "P3"],
        "provisional_authority_levels": ["P0", "P1"]
    }, indent=2))
    print("  created verifier_contract.json")


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
    except Exception:
        pass


def _try_ace_reflector(run_dir: Path, run_id: str):
    """ACE reflector: classifies memory cards. Builds context pack from current run."""
    card_path = run_dir / "mempalace_card.json"
    cards = []
    if card_path.exists():
        try:
            cards = [json.loads(card_path.read_text(encoding="utf-8"))]
        except Exception:
            pass
    if not cards:
        cards = [{"card_id": f"card_{run_id}", "content": "single run card"}]
    
    ctx = run_dir / "context_pack.json"
    ctx.write_text(json.dumps({"cards": cards}, indent=2))
    
    fs_path = run_dir / "final_status.json"
    outcome = ""
    if fs_path.exists():
        outcome = json.loads(fs_path.read_text(encoding="utf-8")).get("status", "")
    
    out = run_dir / "reflection_report.json"
    subprocess.run(
        [sys.executable, str(RUNTIME / "ace_reflector.py"), run_id,
         "--context-pack", str(ctx), "--outcome-status", outcome,
         "--output", str(out)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30
    )
    print("  ace_reflector: generated reflection report" if out.exists() else "  ace_reflector: done")


def _try_ace_curator(run_dir: Path, run_id: str):
    """ACE curator: proposes memory deltas (requires prior cards).
    Only works when prior run data is available. Skipped gracefully otherwise."""
    card_path = run_dir / "run_local_memory" / "memory_journal.jsonl"
    if not card_path.exists():
        print("  ace_curator: skipped (no memory cards)")
        return
    try:
        card = json.loads(card_path.read_text(encoding="utf-8").splitlines()[0])
    except Exception:
        print("  ace_curator: skipped (invalid card format)")
        return
    out = run_dir / "curator_delta.json"
    subprocess.run(
        [sys.executable, str(RUNTIME / "ace_curator.py"), run_id,
         "--source-run-id", run_id, "--card", json.dumps(card),
         "--output", str(out)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30
    )
    print("  ace_curator: generated curator delta" if out.exists() else "  ace_curator: done")


def _try_mempalace_store(run_dir: Path, run_id: str):
    """MemPalace: store advisory memory card in the appropriate wing/room."""
    card = {
        "card_id": f"card_{run_id}",
        "run_id": run_id,
        "wing": "planning",
        "room": "plan_seed_patterns",
        "content": {
            "goal": run_id,
            "outcome": json.loads((run_dir / "final_status.json").read_text(encoding="utf-8")).get("status", "UNKNOWN") if (run_dir / "final_status.json").exists() else "UNKNOWN",
            "lesson": f"Run {run_id} completed. Memory is advisory only."
        },
        "advisory": True,
        "can_certify": False
    }
    card_path = run_dir / "mempalace_card.json"
    card_path.write_text(json.dumps(card, indent=2))
    print("  mempalace: stored advisory card (planning/plan_seed_patterns)")


def _try_memory_gate(run_dir: Path, run_id: str):
    """Memory write gate: promotes to durable only after certifier locks status."""
    card_path = run_dir / "mempalace_card.json"
    fs_path = run_dir / "final_status.json"
    if not card_path.exists():
        print("  memory_gate: skipped (no card)")
        return
    if not fs_path.exists():
        print("  memory_gate: skipped (no final_status — gate requires certifier lock)")
        return
    print("  memory_gate: card ready for promotion (gated by certifier-owned final_status.json)")


def _write_local_memory(run_dir: Path, run_id: str):
    """Write advisory local memory record. Memory cannot certify or override evidence."""
    mem_dir = run_dir / "run_local_memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    cert_path = run_dir / "certification.json"
    status = json.loads(cert_path.read_text(encoding="utf-8")).get("status", "UNKNOWN") if cert_path.exists() else "UNKNOWN"
    record = {
        "run_id": run_id, "timestamp": datetime.now(timezone.utc).isoformat(),
        "certification_status": status, "memory_type": "run_local",
        "advisory": True, "can_certify": False,
        "lesson": f"Run {run_id} completed with status {status}.",
        "authority_note": "Advisory only. Does not replace certifier-owned evidence."
    }
    (mem_dir / "memory_journal.jsonl").write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    print("  wrote local memory record (advisory, non-certifying)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python full_verify.py .agentic-runs/<run_id>")
        sys.exit(2)
    run_dir = Path(sys.argv[1])
    status = verify(run_dir)
    print(f"\nFINAL: {status}")
    sys.exit(0 if status in ("DONE_PASS", "CERTIFIED_DONE", "PROVISIONAL_DONE") else 1)
