"""
Adversarial testing loop for the harness.

After certification, spawn a skeptic agent to try to break the solution.
If it finds a break → bug report → repair loop → re-certify.
Continues until no more breaks found or max iterations reached.

Usage:
    python adversarial_loop.py <run_dir> [--max-rounds 3]
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def extract_code(run_dir: Path) -> dict:
    """Read the solution code from the run directory."""
    gc_path = run_dir / "goal_contract.json"
    if not gc_path.exists():
        return {}
    gc = json.loads(gc_path.read_text(encoding="utf-8"))
    outputs = gc.get("final_outputs", [])
    code = {}
    for output in outputs:
        path = run_dir / output
        if path.exists():
            code[output] = path.read_text(encoding="utf-8")
    return code


def build_skeptic_prompt(run_dir: Path, code: dict, round_num: int) -> str:
    """Build a prompt for the skeptic to find edge case failures."""
    run_id = run_dir.name
    
    prompt = f"""You are an adversarial tester. Find edge cases that break this code.

Run ID: {run_id}
Round: {round_num}

## Code to Attack

"""
    for name, content in code.items():
        prompt += f"### {name}\n```python\n{content}\n```\n\n"
    
    prompt += """## Instructions

1. Read the code carefully. Understand what it claims to do.
2. Find inputs that would produce wrong results or crashes.
3. Test your edge cases mentally — verify they would actually break.
4. If you find a break, output exactly this JSON:

```json
{
  "found_break": true,
  "input": [<test inputs>],
  "expected": <what should happen>,
  "actual_bug": <what actually happens>,
  "severity": "crash|wrong_output|edge_case",
  "fix_suggestion": "How to fix"
}
```

5. If the code is solid and you cannot find any breaks, output:

```json
{
  "found_break": false,
  "analysis": "Why the code is correct"
}
```

Do NOT write code. Do NOT edit files. Only analyze and report."""
    
    return prompt


def run_skeptic(run_dir: Path, round_num: int) -> dict:
    """Run the skeptic agent and parse its output."""
    code = extract_code(run_dir)
    if not code:
        return {"found_break": False, "analysis": "No code found to test"}
    
    prompt = build_skeptic_prompt(run_dir, code, round_num)
    
    # Write prompt for the skeptic agent
    prompt_path = run_dir / f"adversarial_prompt_{round_num}.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    
    print(f"  Skeptic prompt: {prompt_path}")
    print(f"  Round {round_num}: testing {len(code)} file(s)...")
    
    # The skeptic agent output would come from Pi — we just prepare the prompt
    # and report what to do next
    return {
        "prompt_path": str(prompt_path),
        "round": round_num,
        "instruction": f"Spawn skeptic-planner agent with prompt at {prompt_path}"
    }


def apply_repair(run_dir: Path, bug_report: dict) -> dict:
    """Generate a repair prompt from a bug report."""
    repair_prompt = f"""run_id={run_dir.name}

## Bug Found by Adversarial Testing

Input: {bug_report.get('input')}
Expected: {bug_report.get('expected')}
Actual Bug: {bug_report.get('actual_bug')}
Severity: {bug_report.get('severity')}
Fix: {bug_report.get('fix_suggestion')}

## Instructions
1. Read harness-repair skill at skills/harness-repair/SKILL.md
2. Read the file that needs fixing
3. Apply the fix suggested above
4. Write the fixed file
5. Read-back to verify
6. Do NOT touch certification.json, final_status.json, policy_decision.json
"""
    
    repair_path = run_dir / "adversarial_repair_prompt.md"
    repair_path.write_text(repair_prompt, encoding="utf-8")
    
    return {
        "repair_path": str(repair_path),
        "bug": bug_report
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python adversarial_loop.py <run_dir> [--max-rounds 3]")
        sys.exit(1)
    
    run_dir = Path(sys.argv[1])
    max_rounds = 3
    if "--max-rounds" in sys.argv:
        max_rounds = int(sys.argv[sys.argv.index("--max-rounds") + 1])
    
    run_id = run_dir.name
    print(f"=== Adversarial Loop: {run_id} (max {max_rounds} rounds) ===\n")
    
    for round_num in range(1, max_rounds + 1):
        result = run_skeptic(run_dir, round_num)
        
        # Write round report
        report = {
            "run_id": run_id,
            "round": round_num,
            "adversarial_result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        report_dir = run_dir / "adversarial_reports"
        report_dir.mkdir(exist_ok=True)
        report_path = report_dir / f"round_{round_num}.json"
        report_path.write_text(json.dumps(report, indent=2))
        
        print(f"  Report: {report_path}")
        print(f"  Next: spawn skeptic-planner agent with the prompt above")
        print(f"  Then: if break found, spawn guarded-worker repair agent")
        print()
    
    print(f"Adversarial loop complete. Check {report_dir}/ for reports.")
    print(f"Summary: skeptic prompts ready — spawn agents to execute each round.")


if __name__ == "__main__":
    main()
