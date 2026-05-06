import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
import hashlib

root = Path.cwd()
run_id = "sample_run_001"
run_dir = root / ".agentic-runs" / run_id
step_dir = run_dir / "step_logs"
artifact_dir = run_dir / "artifacts"

step_dir.mkdir(parents=True, exist_ok=True)
artifact_dir.mkdir(parents=True, exist_ok=True)

# Normalize sample goal contract into run folder without BOM
sample_goal = root / ".agentic-pi" / "examples" / "sample_goal_contract.json"
with sample_goal.open("r", encoding="utf-8-sig") as f:
    goal = json.load(f)

(run_dir / "goal_contract.json").write_text(
    json.dumps(goal, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

# Create final artifact
readme = root / "README.md"
readme.write_text(
"""# Mercury Goal Runner Harness v0.1

This harness controls Mercury V2 as a fast worker inside a verified goal-execution system.

## Core parts

1. Prompt Compiler  
Converts a rough user goal into a structured Goal Contract.

2. Goal Contract  
Defines the cleaned goal, final outputs, constraints, done criteria, and failure criteria.

3. Guarded Worker  
Executes one approved step at a time and reports evidence.

4. Trace Logger  
Records what happened during the run.

5. Certifier  
Checks evidence, required files, logs, and done criteria before marking DONE_PASS.

## Core rule

Mercury may propose, plan, execute, and report, but it cannot certify final success.

Evidence beats confidence.
""",
    encoding="utf-8"
)

# Create step log
step_result = {
    "run_id": run_id,
    "step_id": 1,
    "status": "PASSED",
    "action_taken": "Created README.md explaining the v0.1 harness architecture.",
    "files_touched": ["README.md"],
    "commands_run": ["python smoke_v01.py"],
    "evidence": [
        "README.md exists.",
        "README.md explains Prompt Compiler, Goal Contract, Guarded Worker, Trace Logger, and Certifier."
    ],
    "pass_condition_satisfied": True,
    "remaining_work": []
}

(step_dir / "001.json").write_text(
    json.dumps(step_result, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

# Create trace event
def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

trace_event = {
    "time": datetime.now(timezone.utc).isoformat(),
    "agent": "guarded-worker",
    "event": "README_CREATED",
    "status": "OK",
    "data": {"file": "README.md"},
    "data_hash": sha256_text(json.dumps({"file": "README.md"}, sort_keys=True))
}

with (run_dir / "trace.jsonl").open("a", encoding="utf-8") as f:
    f.write(json.dumps(trace_event, ensure_ascii=False) + "\n")

# Run certifier
cmd = [
    sys.executable,
    ".agentic-pi\\validators\\certify_run.py",
    str(run_dir)
]

result = subprocess.run(cmd, text=True)
sys.exit(result.returncode)