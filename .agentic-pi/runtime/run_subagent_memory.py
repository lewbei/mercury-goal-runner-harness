"""
Subagent memory capture pipeline (self-contained, no MCP).

After a Pi subagent completes its work, this script:
1. Reads the subagent's outputs (thinking_plan.md, step_logs)
2. Creates an ACE reflection report
3. Extracts learning candidates
4. Writes to project-local .agentic-pi/memory/durable/

Usage:
    python run_subagent_memory.py <run_dir> <agent_name>
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_subagent_memory.py <run_dir> [agent_name]")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    agent_name = sys.argv[2] if len(sys.argv) > 2 else "unknown-agent"
    run_id = run_dir.name

    if not run_dir.exists():
        print(f"Error: run directory not found: {run_dir}")
        sys.exit(1)

    print(f"=== Subagent Memory Capture: {agent_name} on {run_id} ===")

    # Step 1: Gather context pack from subagent outputs
    context_pack = []
    tp = run_dir / "thinking_plan.md"
    if tp.exists():
        context_pack.append({
            "card_id": f"plan-{run_id}",
            "content": tp.read_text(encoding="utf-8")[:500],
            "source": "thinking_plan",
            "room": "harness-plans"
        })

    for sl in sorted((run_dir / "step_logs").glob("*.json")) if (run_dir / "step_logs").is_dir() else []:
        try:
            log = json.loads(sl.read_text(encoding="utf-8"))
            context_pack.append({
                "card_id": f"step-{run_id}-{sl.stem}",
                "content": log.get("evidence", ["No evidence"])[0] if log.get("evidence") else "No evidence",
                "source": "step_log",
                "room": "harness-steps"
            })
        except Exception:
            pass

    if not context_pack:
        print("  No context pack data found")
    else:
        print(f"  Context pack: {len(context_pack)} entries")

    # Step 2: Read final status for outcome
    outcome = "UNKNOWN"
    fs_path = run_dir / "final_status.json"
    if fs_path.exists():
        try:
            fs = json.loads(fs_path.read_text(encoding="utf-8"))
            outcome = fs.get("status", "UNKNOWN")
        except Exception:
            pass

    # Step 3: Build reflection
    helpful = []
    harmful = []
    if outcome in ("CERTIFIED_DONE", "DONE_PASS"):
        for card in context_pack:
            helpful.append({"card_id": card["card_id"], "reason": f"Contributed to {outcome}"})
    elif outcome in ("NOT_DONE", "DONE_FAIL"):
        for card in context_pack:
            harmful.append({"card_id": card["card_id"], "reason": f"Did not prevent {outcome}"})

    reflection = {
        "schema_version": "reflection_report_v1",
        "run_id": run_id,
        "agent_name": agent_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "outcome_status": outcome,
        "helpful": helpful,
        "harmful": harmful,
        "neutral": []
    }

    ref_path = run_dir / "run_local_memory" / "ace_reflection.json"
    ref_path.parent.mkdir(exist_ok=True)
    ref_path.write_text(json.dumps(reflection, indent=2))
    print(f"  Reflection: {len(helpful)} helpful, {len(harmful)} harmful -> {ref_path}")

    # Step 4: Extract learning candidates
    learning = []
    for card in context_pack:
        learning.append({
            "card_id": f"learn-{run_id}-{agent_name}-{len(learning)}",
            "content": f"Subagent {agent_name} in {run_id}: {card['content'][:200]}",
            "source": card["source"],
            "agent": agent_name,
            "outcome": outcome
        })

    learn_path = run_dir / "run_local_memory" / "learning_candidates.json"
    learn_path.write_text(json.dumps(learning, indent=2))
    print(f"  Learning candidates: {len(learning)} -> {learn_path}")

    # Step 5: Store in project-local durable memory
    memory_root = ROOT / ".agentic-pi" / "memory"
    for lc in learning:
        # Classify: algorithm/design → planning, else → verification
        content_lower = lc["content"].lower()
        if any(w in content_lower for w in ("algorithm", "design", "plan", "architecture")):
            room = "planning"
        else:
            room = "verification"
        
        card_path = memory_root / "durable" / room / f"{lc['card_id']}.json"
        card_path.parent.mkdir(exist_ok=True)
        record = {
            "card_id": lc["card_id"],
            "content": lc["content"],
            "source": lc["source"],
            "agent": lc.get("agent", agent_name),
            "outcome": lc.get("outcome", outcome),
            "stored_at": datetime.now(timezone.utc).isoformat()
        }
        card_path.write_text(json.dumps(record, indent=2))
        print(f"  Durable memory: {card_path.relative_to(ROOT)}")

    # Step 6: Write memory journal entry
    journal_path = run_dir / "memory_journal.jsonl"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent_name,
        "run_id": run_id,
        "action": "memory_capture",
        "reflection": f"{len(helpful)} helpful / {len(harmful)} harmful",
        "learning_candidates": len(learning),
        "outcome": outcome
    }
    with journal_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"  Journal entry: {journal_path}")

    print(f"=== Memory capture complete for {agent_name} ===")


if __name__ == "__main__":
    main()
