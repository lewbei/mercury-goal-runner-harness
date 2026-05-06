$ErrorActionPreference = "Stop"

$dirs = @(
  ".pi\agents",
  ".agentic-pi\schemas",
  ".agentic-pi\validators",
  ".agentic-pi\runtime",
  ".agentic-pi\security",
  ".agentic-pi\prompts",
  ".agentic-pi\skills",
  ".agentic-pi\examples",
  ".agentic-runs"
)

foreach ($d in $dirs) {
  New-Item -ItemType Directory -Force -Path $d | Out-Null
}

function Write-Text {
  param(
    [string]$Path,
    [string]$Content
  )
  $parent = Split-Path $Path -Parent
  if ($parent -and !(Test-Path $parent)) {
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
  }
  Set-Content -Path $Path -Value $Content -Encoding UTF8
}

Write-Text ".agentic-pi\config.json" @'
{
  "project_name": "mercury-goal-runner-harness",
  "version": "0.1.0",
  "default_runtime_model": "inception/mercury-2",
  "strong_review_model": "gpt-5.5",
  "status_values": [
    "INIT_READY",
    "CONTRACT_READY",
    "PLANNING",
    "PLAN_READY",
    "EXECUTING",
    "OBSERVING",
    "CERTIFYING",
    "DONE_PASS",
    "DONE_FAIL",
    "BLOCKED",
    "NEED_USER",
    "MAX_STEPS_REACHED"
  ],
  "protected_paths": [
    ".agentic-pi/state.json",
    ".agentic-runs/**/trace.jsonl",
    ".agentic-runs/**/certification.json",
    ".agentic-runs/**/final_status.md"
  ],
  "rules": [
    "Mercury may propose, but cannot certify final PASS.",
    "Worker agents cannot edit protected files.",
    "Every goal must become a Goal Contract before execution.",
    "Every DONE requires evidence.",
    "Repeated failure becomes BLOCKED, not infinite retry."
  ]
}
'@

Write-Text ".agentic-pi\state.json" @'
{
  "version": "0.1.0",
  "current_run_id": null,
  "last_status": "INIT_READY"
}
'@

Write-Text ".agentic-pi\state_machine.md" @'
# Mercury Goal Runner State Machine

INIT_READY
  -> CONTRACT_READY
  -> PLANNING
  -> PLAN_READY
  -> EXECUTING
  -> OBSERVING
  -> CERTIFYING
  -> DONE_PASS | DONE_FAIL | BLOCKED | NEED_USER | MAX_STEPS_REACHED

Rules:
- No raw user goal is executed directly.
- A Goal Contract must exist before planning.
- A plan must exist before execution.
- A step log must exist before certification.
- Only certifier logic writes certification.json and final_status.md.
- If the same failure repeats twice, mark BLOCKED.
- If evidence is missing, do not mark DONE_PASS.
'@

Write-Text ".agentic-pi\schemas\goal_contract.schema.json" @'
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "GoalContract",
  "type": "object",
  "required": [
    "run_id",
    "raw_user_prompt",
    "intent",
    "cleaned_goal",
    "final_outputs",
    "explicit_constraints",
    "inferred_constraints",
    "forbidden_actions",
    "ambiguities",
    "risk_level",
    "complexity_level",
    "done_criteria",
    "failure_criteria",
    "ask_user_conditions",
    "max_steps",
    "execution_prompt"
  ],
  "properties": {
    "run_id": { "type": "string" },
    "raw_user_prompt": { "type": "string" },
    "intent": { "type": "string" },
    "cleaned_goal": { "type": "string" },
    "final_outputs": {
      "type": "array",
      "items": { "type": "string" }
    },
    "explicit_constraints": {
      "type": "array",
      "items": { "type": "string" }
    },
    "inferred_constraints": {
      "type": "array",
      "items": { "type": "string" }
    },
    "forbidden_actions": {
      "type": "array",
      "items": { "type": "string" }
    },
    "ambiguities": {
      "type": "array",
      "items": { "type": "string" }
    },
    "risk_level": {
      "type": "string",
      "enum": ["LOW", "MEDIUM", "HIGH"]
    },
    "complexity_level": {
      "type": "string",
      "enum": ["SIMPLE", "MEDIUM", "HARD", "RISKY"]
    },
    "done_criteria": {
      "type": "array",
      "items": { "type": "string" }
    },
    "failure_criteria": {
      "type": "array",
      "items": { "type": "string" }
    },
    "ask_user_conditions": {
      "type": "array",
      "items": { "type": "string" }
    },
    "max_steps": { "type": "integer" },
    "execution_prompt": { "type": "string" }
  },
  "additionalProperties": false
}
'@

Write-Text ".agentic-pi\schemas\step_result.schema.json" @'
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "StepResult",
  "type": "object",
  "required": [
    "run_id",
    "step_id",
    "status",
    "action_taken",
    "files_touched",
    "commands_run",
    "evidence",
    "pass_condition_satisfied",
    "remaining_work"
  ],
  "properties": {
    "run_id": { "type": "string" },
    "step_id": { "type": "integer" },
    "status": {
      "type": "string",
      "enum": ["PASSED", "FAILED_REPAIRABLE", "BLOCKED", "NEED_USER"]
    },
    "action_taken": { "type": "string" },
    "files_touched": {
      "type": "array",
      "items": { "type": "string" }
    },
    "commands_run": {
      "type": "array",
      "items": { "type": "string" }
    },
    "evidence": {
      "type": "array",
      "items": { "type": "string" }
    },
    "pass_condition_satisfied": { "type": "boolean" },
    "remaining_work": {
      "type": "array",
      "items": { "type": "string" }
    }
  },
  "additionalProperties": false
}
'@

Write-Text ".agentic-pi\schemas\certification.schema.json" @'
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Certification",
  "type": "object",
  "required": [
    "run_id",
    "status",
    "passed_checks",
    "failed_checks",
    "artifact_hashes",
    "audit_chain_valid",
    "generated_by",
    "timestamp"
  ],
  "properties": {
    "run_id": { "type": "string" },
    "status": {
      "type": "string",
      "enum": ["DONE_PASS", "DONE_FAIL", "BLOCKED", "NEED_USER", "MAX_STEPS_REACHED"]
    },
    "passed_checks": {
      "type": "array",
      "items": { "type": "string" }
    },
    "failed_checks": {
      "type": "array",
      "items": { "type": "string" }
    },
    "artifact_hashes": {
      "type": "object"
    },
    "audit_chain_valid": { "type": "boolean" },
    "generated_by": { "type": "string" },
    "timestamp": { "type": "string" }
  },
  "additionalProperties": false
}
'@

Write-Text ".agentic-pi\security\command_policy.json" @'
{
  "version": "0.1.0",
  "default_policy": "deny_risky_without_approval",
  "safe_commands": [
    "dir",
    "tree",
    "type",
    "more",
    "findstr",
    "python",
    "git status",
    "git diff"
  ],
  "medium_risk_commands": [
    "pip install",
    "npm install",
    "pytest",
    "python -m pytest",
    "git add",
    "git commit"
  ],
  "high_risk_commands_require_approval": [
    "del",
    "rmdir",
    "move",
    "ren",
    "git reset",
    "git clean",
    "curl",
    "powershell -Command",
    "Invoke-WebRequest",
    "iwr"
  ],
  "forbidden_patterns": [
    "rm -rf",
    "curl | bash",
    "iwr .* | iex",
    "Invoke-Expression",
    "setx .*KEY",
    "echo .*API_KEY",
    "git push",
    "format ",
    "cipher /w"
  ],
  "protected_paths": [
    ".agentic-pi/state.json",
    ".agentic-runs/**/trace.jsonl",
    ".agentic-runs/**/certification.json",
    ".agentic-runs/**/final_status.md"
  ]
}
'@

Write-Text ".agentic-pi\skills\mental_model.md" @'
# Mental Model

Mercury V2 is a fast worker inside a controlled harness, not the final authority.

Core loop:
rough goal -> goal contract -> plan -> execute one step -> observe evidence -> certify or repair.

Rules:
1. Do not execute raw messy prompts directly.
2. Every goal needs final outputs, constraints, DONE criteria, and stop conditions.
3. Evidence beats confidence.
4. Mercury may propose PASS, but only the certifier can mark PASS.
5. If done cannot be proven from artifacts/logs, the task is not done.
6. If the same failure repeats, stop and mark BLOCKED instead of looping.
'@

Write-Text ".agentic-pi\skills\governance_model.md" @'
# Governance Model

This harness uses a constitutional executor model.

Branches:
1. Constitution: hard rules and forbidden actions.
2. CEO / Orchestrator: routes, approves, stops, requests repair.
3. Planners: propose plans.
4. Skeptic: attacks risks and fake-DONE.
5. Worker: executes one approved step.
6. Supervisor: watches drift and repeated failure.
7. Certifier: decides PASS / FAIL / BLOCKED from evidence.

Core rule:
Planner proposes.
Worker executes.
Supervisor watches.
Certifier decides.
Mercury cannot certify itself.
'@

Write-Text ".agentic-pi\prompts\prompt_compiler.md" @'
You are the Prompt Compiler for Mercury Goal Runner.

Your job is not to solve the task.
Your job is to convert the user rough goal into a valid Goal Contract.

Return valid JSON only.

Required fields:
{
  "run_id": "",
  "raw_user_prompt": "",
  "intent": "",
  "cleaned_goal": "",
  "final_outputs": [],
  "explicit_constraints": [],
  "inferred_constraints": [],
  "forbidden_actions": [],
  "ambiguities": [],
  "risk_level": "LOW|MEDIUM|HIGH",
  "complexity_level": "SIMPLE|MEDIUM|HARD|RISKY",
  "done_criteria": [],
  "failure_criteria": [],
  "ask_user_conditions": [],
  "max_steps": 20,
  "execution_prompt": ""
}

Rules:
- Preserve the user's real intention.
- Do not over-expand the goal.
- Do not solve the task.
- If assumptions are needed, state them.
- If done criteria are missing, create objective criteria.
- Never produce empty final_outputs.
- Never produce empty done_criteria.
'@

Write-Text ".agentic-pi\prompts\guarded_worker.md" @'
You are the Guarded Worker.

You execute only ONE approved step at a time.

Rules:
- Do not mark final DONE.
- Do not touch protected files.
- Do not invent success.
- Report evidence after the step.
- If the step is unclear, stop and request clarification.

Protected files:
- .agentic-pi/state.json
- .agentic-runs/**/trace.jsonl
- .agentic-runs/**/certification.json
- .agentic-runs/**/final_status.md

Your output must include:
1. action_taken
2. files_touched
3. commands_run
4. evidence
5. pass_condition_satisfied
6. remaining_work
'@

Write-Text ".pi\agents\prompt-compiler.md" @'
---
name: prompt-compiler
description: Converts rough user goals into executable goal contracts
model: inception/mercury-2
thinking: high
systemPromptMode: replace
inheritProjectContext: true
inheritSkills: false
tools: read, ls
---

You are the Prompt Compiler for Mercury Goal Runner.

Read .agentic-pi/prompts/prompt_compiler.md and follow it exactly.

Return valid JSON only.
Do not solve the user task.
'@

Write-Text ".pi\agents\guarded-worker.md" @'
---
name: guarded-worker
description: Executes one approved step at a time and reports evidence
model: inception/mercury-2
thinking: medium
systemPromptMode: replace
inheritProjectContext: true
inheritSkills: false
tools: read, ls, grep, find, bash
---

You are the Guarded Worker.

Read .agentic-pi/prompts/guarded_worker.md and follow it exactly.

You execute only one approved step.
You cannot certify final PASS.
'@

Write-Text ".pi\agents\skeptic-planner.md" @'
---
name: skeptic-planner
description: Finds failure modes and fake-DONE risks before execution
model: inception/mercury-2
thinking: high
systemPromptMode: replace
inheritProjectContext: true
inheritSkills: false
tools: read, ls, grep
---

You are the Skeptic Planner.

Your job:
1. Identify likely failure modes.
2. Identify vague done criteria.
3. Identify unsafe actions.
4. Create safer pass/fail checks.

You do not execute.
You do not certify.
Return structured JSON or markdown only.
'@

Write-Text ".agentic-pi\validators\validate_schema.py" @'
import json
import sys
from pathlib import Path

TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "boolean": bool
}

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def validate(instance, schema, loc="$"):
    errors = []

    expected_type = schema.get("type")
    if expected_type:
        py_type = TYPE_MAP.get(expected_type)
        if py_type and not isinstance(instance, py_type):
            errors.append(f"{loc}: expected {expected_type}, got {type(instance).__name__}")
            return errors

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{loc}: value {instance!r} not in enum {schema['enum']}")

    if expected_type == "object":
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{loc}: missing required field {key}")

        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance.keys():
                if key not in props:
                    errors.append(f"{loc}: unexpected field {key}")

        for key, subschema in props.items():
            if key in instance:
                errors.extend(validate(instance[key], subschema, f"{loc}.{key}"))

    if expected_type == "array":
        item_schema = schema.get("items", {})
        for i, item in enumerate(instance):
            errors.extend(validate(item, item_schema, f"{loc}[{i}]"))

    return errors

def main():
    if len(sys.argv) != 3:
        print("Usage: python validate_schema.py <schema.json> <instance.json>")
        sys.exit(2)

    schema_path = Path(sys.argv[1])
    instance_path = Path(sys.argv[2])

    schema = load_json(schema_path)
    instance = load_json(instance_path)

    errors = validate(instance, schema)

    if errors:
        print("SCHEMA_INVALID")
        for e in errors:
            print(f"- {e}")
        sys.exit(1)

    print("SCHEMA_VALID")

if __name__ == "__main__":
    main()
'@

Write-Text ".agentic-pi\runtime\trace_logger.py" @'
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--agent", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--status", default="OK")
    parser.add_argument("--data", default="{}")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        data_obj = json.loads(args.data)
    except json.JSONDecodeError:
        data_obj = {"raw": args.data}

    event = {
        "time": datetime.now(timezone.utc).isoformat(),
        "agent": args.agent,
        "event": args.event,
        "status": args.status,
        "data": data_obj,
        "data_hash": sha256_text(json.dumps(data_obj, sort_keys=True))
    }

    trace_path = run_dir / "trace.jsonl"
    with trace_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    print(f"TRACE_WRITTEN {trace_path}")

if __name__ == "__main__":
    main()
'@

Write-Text ".agentic-pi\validators\certify_run.py" @'
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROTECTED_NAMES = {
    "certification.json",
    "final_status.md",
    "trace.jsonl"
}

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

def main():
    if len(sys.argv) != 2:
        print("Usage: python certify_run.py <run_dir>")
        sys.exit(2)

    project_root = Path.cwd()
    run_dir = Path(sys.argv[1])

    passed = []
    failed = []
    artifact_hashes = {}

    if not run_dir.exists():
        print("RUN_DIR_MISSING")
        sys.exit(1)

    run_id = run_dir.name
    goal_path = run_dir / "goal_contract.json"
    trace_path = run_dir / "trace.jsonl"
    step_dir = run_dir / "step_logs"

    if goal_path.exists():
        passed.append("goal_contract.json exists")
        try:
            goal = load_json(goal_path)
            passed.append("goal_contract.json parses as JSON")
        except Exception as e:
            goal = None
            failed.append(f"goal_contract.json parse failed: {e}")
    else:
        goal = None
        failed.append("goal_contract.json missing")

    if trace_path.exists():
        passed.append("trace.jsonl exists")
        try:
            for line_no, line in enumerate(trace_path.read_text(encoding="utf-8").splitlines(), start=1):
                if line.strip():
                    json.loads(line)
            passed.append("trace.jsonl lines parse as JSON")
        except Exception as e:
            failed.append(f"trace.jsonl invalid at line {line_no}: {e}")
    else:
        failed.append("trace.jsonl missing")

    if step_dir.exists():
        logs = sorted(step_dir.glob("*.json"))
        if logs:
            passed.append("step_logs contain at least one step result")
        else:
            failed.append("step_logs exists but contains no .json files")
    else:
        logs = []
        failed.append("step_logs directory missing")

    for log in logs:
        try:
            step = load_json(log)
            touched = step.get("files_touched", [])
            evidence = step.get("evidence", [])
            if evidence:
                passed.append(f"{log.name} contains evidence")
            else:
                failed.append(f"{log.name} has empty evidence")

            for p in touched:
                name = Path(p).name
                if name in PROTECTED_NAMES:
                    failed.append(f"{log.name} reports Worker touched protected file: {p}")
        except Exception as e:
            failed.append(f"{log.name} parse failed: {e}")

    if goal:
        final_outputs = goal.get("final_outputs", [])
        done_criteria = goal.get("done_criteria", [])

        if done_criteria:
            passed.append("done_criteria is non-empty")
        else:
            failed.append("done_criteria is empty")

        if final_outputs:
            passed.append("final_outputs is non-empty")
            for output in final_outputs:
                output_path = project_root / output
                if output_path.exists():
                    passed.append(f"final output exists: {output}")
                    if output_path.is_file():
                        artifact_hashes[output] = sha256_file(output_path)
                else:
                    failed.append(f"final output missing: {output}")
        else:
            failed.append("final_outputs is empty")

    status = "DONE_PASS" if not failed else "DONE_FAIL"

    certification = {
        "run_id": run_id,
        "status": status,
        "passed_checks": passed,
        "failed_checks": failed,
        "artifact_hashes": artifact_hashes,
        "audit_chain_valid": True,
        "generated_by": "agentic-pi-certifier-v0.1",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    cert_path = run_dir / "certification.json"
    final_status_path = run_dir / "final_status.md"

    write_json(cert_path, certification)

    report = []
    report.append(f"# Final Status: {status}")
    report.append("")
    report.append(f"Run ID: `{run_id}`")
    report.append("")
    report.append("## Passed checks")
    for item in passed:
        report.append(f"- {item}")
    report.append("")
    report.append("## Failed checks")
    if failed:
        for item in failed:
            report.append(f"- {item}")
    else:
        report.append("- none")
    report.append("")
    report.append("## Artifact hashes")
    if artifact_hashes:
        for k, v in artifact_hashes.items():
            report.append(f"- `{k}`: `{v}`")
    else:
        report.append("- none")

    final_status_path.write_text("\n".join(report), encoding="utf-8")

    print(status)
    print(f"Wrote {cert_path}")
    print(f"Wrote {final_status_path}")

    if failed:
        sys.exit(1)

if __name__ == "__main__":
    main()
'@

Write-Text ".agentic-pi\examples\sample_goal_contract.json" @'
{
  "run_id": "sample_run_001",
  "raw_user_prompt": "Create a README explaining the Mercury Goal Runner v0.1 architecture.",
  "intent": "Create a short documentation artifact for the harness.",
  "cleaned_goal": "Create README.md explaining the v0.1 Mercury Goal Runner Harness architecture.",
  "final_outputs": ["README.md"],
  "explicit_constraints": ["Keep v0.1 small."],
  "inferred_constraints": ["Do not add memory or multi-agent mode yet."],
  "forbidden_actions": ["Do not mark DONE without evidence.", "Do not touch protected files."],
  "ambiguities": [],
  "risk_level": "LOW",
  "complexity_level": "SIMPLE",
  "done_criteria": [
    "README.md exists.",
    "README.md explains Prompt Compiler, Goal Contract, Worker, Trace Logger, and Certifier."
  ],
  "failure_criteria": [
    "README.md is missing.",
    "Worker touches protected files."
  ],
  "ask_user_conditions": [
    "Ask user if source edits outside README.md are required."
  ],
  "max_steps": 5,
  "execution_prompt": "Create README.md explaining the v0.1 Mercury Goal Runner Harness architecture. Do not touch protected files."
}
'@

Write-Text ".gitignore" @'
__pycache__/
*.pyc
.agentic-runs/*/backups/
.agentic-runs/*/diffs/
.env
.env.*
'@

Write-Host ""
Write-Host "V0.1 scaffold created."
Write-Host "Next checks:"
Write-Host "  python .agentic-pi\validators\validate_schema.py .agentic-pi\schemas\goal_contract.schema.json .agentic-pi\examples\sample_goal_contract.json"
Write-Host "  tree /F"
Write-Host "  git status"