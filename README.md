# Simple Goal

This harness controls Mercury V2 as a fast worker inside a verified goal-execution system.

The goal is not to make Mercury V2 magically smarter by looping. The goal is to place Mercury V2 inside a controlled harness where every goal becomes a contract, every step produces evidence, and final success is certified by deterministic checks.

## Current status

v0.1 is validated.

See [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for the proof summary and current limitations.

The main proof run is:

```text
.agentic-runs/real_goal_001/
```

It demonstrates:

1. a Goal Contract was created,
2. a Guarded Worker created the requested documentation artifact,
3. an empty-evidence Worker log was rejected,
4. the step log was repaired with evidence,
5. and the certifier issued `DONE_PASS`.

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
Checks evidence, required files, logs, and done criteria before marking `DONE_PASS`.

## Core rule

Mercury may propose, plan, execute, and report, but it cannot certify final success.

Evidence beats confidence.

## Quick validation commands

Validate a Goal Contract:

```cmd
python .agentic-pi\validators\validate_schema.py .agentic-pi\schemas\goal_contract.schema.json .agentic-runs\real_goal_001\goal_contract.json
```

Validate a Worker step log:

```cmd
python .agentic-pi\validators\validate_schema.py .agentic-pi\schemas\step_result.schema.json .agentic-runs\real_goal_001\step_logs\001.json
```

Run certification:

```cmd
python .agentic-pi\validators\certify_run.py .agentic-runs\real_goal_001
```

Run the deterministic smoke test:

```cmd
python smoke_v01.py
```

## Next milestone

v0.2 should add automatic run creation and a small command-line runner so the harness no longer needs manual run-folder setup.
