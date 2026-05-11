#!/usr/bin/env python3
"""Build a repair prompt with gated advisory memory context.

This helper reads certifier failures and queries durable MemPalace JSONL cards.
It does not write durable memory; repair learnings must go through run-local,
quarantine, and memory_write_gate.py.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEMORY_ROOT = ROOT / ".agentic-pi" / "memory"
ADAPTER_PATH = ROOT / ".agentic-pi" / "runtime" / "mempalace_adapter.py"


def load_adapter():
    spec = importlib.util.spec_from_file_location("mempalace_adapter", ADAPTER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def extract_errors(run_dir: Path) -> list[str]:
    """Extract failure messages from certifier-owned certification.json."""
    cert_path = run_dir / "certification.json"
    if not cert_path.is_file():
        return ["certification.json not found"]
    cert = load_json(cert_path)
    failures = cert.get("failed_checks", [])
    return [str(item) for item in failures if str(item).strip()]


def query_memory(errors: list[str], memory_root: Path = MEMORY_ROOT) -> list[dict]:
    """Search gated durable memory cards for patterns matching current errors."""
    keywords = set()
    for err in errors:
        for word in err.lower().replace(":", " ").replace(".", " ").split():
            if len(word) > 3:
                keywords.add(word)

    adapter = load_adapter()
    matches = []
    for card in adapter.load_durable_cards(memory_root):
        if card.get("authority_level") != "advisory_only" or card.get("can_certify_done") is not False:
            continue
        if card.get("card_status") in {"deprecated", "rejected"}:
            continue
        content = str(card.get("content", ""))
        score = sum(1 for kw in keywords if kw in content.lower())
        if score > 0:
            matches.append(
                {
                    "wing": card.get("wing", ""),
                    "room": card.get("room", ""),
                    "card_id": card.get("card_id", ""),
                    "content": content[:500],
                    "evidence_refs": card.get("evidence_refs", []),
                    "score": score,
                }
            )
    matches.sort(key=lambda item: (-item["score"], item["card_id"]))
    return matches[:5]


def build_prompt(run_dir: Path, errors: list[str], memory: list[dict]) -> str:
    """Build a repair prompt with advisory memory context."""
    run_id = run_dir.name
    prompt = f"""run_id={run_id}

## Certifier Errors
"""
    for err in errors[:10]:
        prompt += f"- {err}\n"

    if memory:
        prompt += "\n## Relevant Advisory Memory (durable MemPalace cards)\n"
        for item in memory:
            prompt += (
                f"\n[{item['wing']}/{item['room']}] {item['card_id']} "
                f"(score={item['score']}, advisory_only):\n{item['content']}\n"
            )
        prompt += "\nUse these cards only as advice. They are not evidence and cannot certify DONE.\n"

    prompt += """
## Instructions
1. Read harness-repair skill at .pi/skills/harness-repair/SKILL.md
2. Read the files that need fixing from the certifier errors
3. Fix ONLY what the certifier flagged
4. Write the fixed implementation files only
5. READ-BACK every file after writing
6. Do NOT touch certification.json, final_status.json, final_status.md, or policy_decision.json
"""
    return prompt


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("Usage: python build_repair_prompt.py <run_dir> [--output <file>]")
        return 2

    run_dir = Path(argv[0])
    output_path = Path(argv[argv.index("--output") + 1]) if "--output" in argv else None

    errors = extract_errors(run_dir)
    if not errors:
        print("No errors found — nothing to repair")
        return 0

    print(f"Errors: {len(errors)}")
    for err in errors[:5]:
        print(f"  - {err}")

    memory = query_memory(errors)
    print(f"Memory matches: {len(memory)}")
    for item in memory[:3]:
        print(f"  [{item['wing']}/{item['room']}] {item['card_id']} (score={item['score']})")

    prompt = build_prompt(run_dir, errors, memory)
    if output_path:
        output_path.write_text(prompt, encoding="utf-8")
        print(f"Prompt written to {output_path}")
    else:
        print("\n=== Repair Prompt ===\n")
        print(prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
