# Project Status

## Current version

Mercury Goal Runner Harness v0.1 is now validated as a minimal proof-of-control harness.

The purpose of this repository is not to claim that Mercury V2 becomes smarter by looping. The purpose is to place Mercury V2 inside a controlled goal-execution harness where outputs are checked through contracts, logs, evidence, and certification.

## v0.1 result

Status: PASS

The v0.1 loop demonstrated the following:

1. A rough user goal can be converted into a structured Goal Contract.
2. A Guarded Worker can execute one approved documentation step.
3. The Worker initially produced an incomplete step log with empty evidence.
4. The certifier correctly rejected that run as DONE_FAIL.
5. After evidence was added to the step log, the certifier issued DONE_PASS.
6. The step-result schema was hardened so empty action_taken, files_touched, and evidence are rejected earlier.

## Verified artifacts

The main proof run is:

```text
.agentic-runs/real_goal_001/
```

Important files:

```text
.agentic-runs/real_goal_001/goal_contract.json
.agentic-runs/real_goal_001/step_logs/001.json
.agentic-runs/real_goal_001/trace.jsonl
.agentic-runs/real_goal_001/certification.json
.agentic-runs/real_goal_001/final_status.md
docs/V0_1_USAGE.md
```

The final certified status is:

```text
DONE_PASS
```

## What v0.1 proves

v0.1 proves the core safety principle:

```text
Mercury may propose, plan, execute, and report evidence, but Mercury cannot certify final success.
```

The harness requires:

- a valid Goal Contract,
- a Worker step log,
- non-empty evidence,
- required final outputs,
- a trace log,
- and certifier-issued final status.

## What was hardened

The step-result schema now rejects weak Worker logs by requiring:

- non-empty action_taken,
- at least one files_touched entry,
- and at least one evidence entry.

The schema validator now supports:

- utf-8-sig reading for Windows BOM issues,
- minLength,
- and minItems.

The Guarded Worker prompt now explicitly forbids placeholder empty evidence.

## Known limitations

v0.1 is still intentionally small.

It does not yet include:

- automatic run creation,
- automatic run folder initialization,
- multi-plan generation,
- plan selection and merging,
- task dependency automation,
- rollback,
- replay mode,
- cost budgets,
- or long-term memory.

This is acceptable for v0.1 because the goal was to prove the control loop before adding more agentic complexity.

## Next milestone

v0.2 should add automatic run creation and stricter Worker execution flow.

Recommended next modules:

1. run initializer,
2. run_id generator,
3. automatic goal_contract placement,
4. automatic step-log path creation,
5. stricter certifier checks for pass_condition_satisfied,
6. and a small command-line runner for the v0.1 loop.

After v0.2 is stable, add adaptive multi-plan planning.
