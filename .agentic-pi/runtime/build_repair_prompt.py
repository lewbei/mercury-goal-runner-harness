"""
Memory-aware repair agent prompt builder.

Before spawning a repair agent, this script:
1. Reads certifier failure messages
2. Queries .agentic-pi/memory/durable/ for similar past failures
3. Builds a repair prompt with relevant memory context
4. After repair, stores the new learning

Usage:
    python build_repair_prompt.py <run_dir> --output <prompt_file>
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEMORY_ROOT = ROOT / ".agentic-pi" / "memory" / "durable"


def extract_errors(run_dir: Path) -> list[str]:
    """Extract failure messages from certification.json."""
    cert_path = run_dir / "certification.json"
    if not cert_path.exists():
        return ["certification.json not found"]
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    return cert.get("failed_checks", [])


def query_memory(errors: list[str]) -> list[dict]:
    """Search durable memory for patterns matching current errors."""
    matches = []
    keywords = set()
    for err in errors:
        for word in err.lower().replace(":", " ").replace(".", " ").split():
            if len(word) > 3:
                keywords.add(word)

    for room in MEMORY_ROOT.iterdir():
        if not room.is_dir():
            continue
        for card in room.glob("*.json"):
            try:
                data = json.loads(card.read_text(encoding="utf-8"))
                content = data.get("content", "").lower()
                score = sum(1 for kw in keywords if kw in content)
                if score > 0:
                    matches.append({
                        "room": room.name,
                        "card_id": data.get("card_id", card.stem),
                        "content": data.get("content", "")[:500],
                        "agent": data.get("agent", "unknown"),
                        "outcome": data.get("outcome", "unknown"),
                        "score": score
                    })
            except Exception:
                pass

    matches.sort(key=lambda m: m["score"], reverse=True)
    return matches[:5]  # Top 5 most relevant


def store_repair_learning(run_dir: Path, errors: list[str], fix_summary: str):
    """Store what was learned from this repair."""
    run_id = run_dir.name
    learning = {
        "card_id": f"repair-{run_id}-{len(errors)}",
        "content": f"Repair in {run_id}: {fix_summary}. Errors: {'; '.join(errors[:3])}",
        "source": "repair_loop",
        "agent": "repair-agent",
        "outcome": "repaired",
        "stored_at": datetime.now(timezone.utc).isoformat()
    }
    path = MEMORY_ROOT / "repair" / f"{learning['card_id']}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(learning, indent=2))
    return path


def build_prompt(run_dir: Path, errors: list[str], memory: list[dict]) -> str:
    """Build a repair prompt with memory context."""
    run_id = run_dir.name
    
    prompt = f"""run_id={run_id}

## Certifier Errors
"""
    for err in errors[:10]:
        prompt += f"- {err}\n"
    
    if memory:
        prompt += f"\n## Relevant Past Learnings (from .agentic-pi/memory/durable/)\n"
        for m in memory:
            prompt += f"\n[{m['room']}] {m['card_id']} (score={m['score']}):\n{m['content']}\n"
        prompt += "\nUse these past learnings to avoid repeating known failures.\n"
    
    prompt += f"""
## Instructions
1. Read harness-repair skill at .agentic-pi/skills/harness-repair/SKILL.md
2. Read the files that need fixing (from error messages)
3. Fix ONLY what the certifier flagged
4. Write the fixed files
5. READ-BACK every file after writing
6. Do NOT touch certification.json, final_status.json, policy_decision.json
"""
    return prompt


def main():
    if len(sys.argv) < 2:
        print("Usage: python build_repair_prompt.py <run_dir> [--output <file>]")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    output_path = sys.argv[sys.argv.index("--output") + 1] if "--output" in sys.argv else None
    
    errors = extract_errors(run_dir)
    if not errors:
        print("No errors found — nothing to repair")
        sys.exit(0)
    
    print(f"Errors: {len(errors)}")
    for e in errors[:5]:
        print(f"  - {e}")
    
    memory = query_memory(errors)
    print(f"Memory matches: {len(memory)}")
    for m in memory[:3]:
        print(f"  [{m['room']}] {m['card_id']} (score={m['score']})")
    
    prompt = build_prompt(run_dir, errors, memory)
    
    if output_path:
        Path(output_path).write_text(prompt, encoding="utf-8")
        print(f"Prompt written to {output_path}")
    else:
        print("\n=== Repair Prompt ===\n")
        print(prompt)


if __name__ == "__main__":
    main()
