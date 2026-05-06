import json
from pathlib import Path

root = Path.cwd()
run_id = "real_goal_001"

docs_dir = root / "docs"
docs_dir.mkdir(exist_ok=True)

doc_path = docs_dir / "V0_1_USAGE.md"

doc_path.write_text(
"""# Mercury Goal Runner Harness v0.1 Usage on Windows

## What the harness is

The Mercury Goal Runner Harness is a small controlled agent framework for running Mercury V2 safely.

Mercury can propose, plan, execute approved steps, and report evidence. However, Mercury cannot mark final success by itself.

The harness separates the workflow into:

1. Prompt Compiler
   Converts a rough user goal into a structured goal_contract.json.

2. Goal Contract
   Defines the cleaned goal, final outputs, constraints, done criteria, failure criteria, and execution prompt.

3. Guarded Worker
   Executes one approved step at a time.

4. Trace Logger
   Records important run events in trace.jsonl.

5. Certifier
   Checks evidence, required files, step logs, and final outputs before writing certification.json and final_status.md.

The core rule is:

Mercury may propose success, but only the certifier can mark DONE_PASS.

## How to validate goal_contract.json

Use the local schema validator:

```cmd
python .agentic-pi\\validators\\validate_schema.py .agentic-pi\\schemas\\goal_contract.schema.json .agentic-runs\\real_goal_001\\goal_contract.json