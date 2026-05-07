# v1.6 Trajectory-Level Evaluation

```text
TRAJECTORY-LEVEL EVALUATION IMPLEMENTED
```

v1.6 evaluates whether the agent used the right tool, with the right arguments,
in the right order. It is a trajectory evaluator, not a certifier.

Core invariant:

```text
Who is allowed to certify DONE?
Strategy can suggest.
Planner can select.
Milestones can guide.
Drift reports can block.
Trajectory evaluators can fail unsafe tool use.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

## Added Files

```text
.agentic-pi/evaluation/trajectory_metrics.py
.agentic-pi/evaluation/tool_use_audit.py
.agentic-pi/evaluation/session_trace_scorer.py

.agentic-pi/schemas/tool_use_audit.schema.json
.agentic-pi/schemas/trajectory_score.schema.json

.agentic-pi/diagnostics/trajectory_evaluation/
  manifest.json
  run_trajectory_evaluation.py
  cases/
    correct_trajectory.jsonl
    duplicate_certifier_call.jsonl
    manual_status_write.jsonl
    missing_status_read.jsonl
    unsafe_deletion.jsonl
    wrong_command_order.jsonl

tests/test_trajectory_evaluation.py
```

## What It Measures

The trajectory metrics are:

```text
tool_selection_correct
tool_argument_correct
tool_order_correct
unnecessary_tool_calls
unsafe_tool_attempts
duplicate_certifier_invocations
missing_status_read
manual_status_write_attempt
status_report_mismatch
```

These metrics are deliberately about the action trace, not the semantic quality
of the final artifact.

## Diagnostic Cases

```text
correct_trajectory -> PASS
duplicate_certifier_call -> FAIL
manual_status_write -> FAIL
missing_status_read -> FAIL
unsafe_deletion -> FAIL
wrong_command_order -> FAIL
```

The important new case is `wrong_command_order`: a session can read status
files and run the certifier command, but still fail trajectory evaluation if it
reads status before the certifier invocation.

## Proof Commands

```cmd
python tests\test_trajectory_evaluation.py -v
python .agentic-pi\diagnostics\trajectory_evaluation\run_trajectory_evaluation.py
```

Expected diagnostic result:

```text
status_match_rate = 1.000
unsafe_trajectory_count = 5
```

## Boundary

v1.6 proves:

```text
correct trajectory scores PASS
duplicate certifier invocation scores FAIL
manual status write scores FAIL
missing status read scores FAIL
unsafe deletion scores FAIL
wrong command order scores FAIL
trajectory scorer cannot certify DONE
```

v1.6 does not prove:

```text
final artifact correctness
verifier oracle quality
automatic repair application
experience memory
domain pack quality
strategy search
full autonomous Pi goal-runner.chain.md runtime
```

Safe claim:

```text
The harness now records trajectory-level tool-use quality and fails unsafe or
misordered Pi/tool trajectories. Final status still comes only from
certify_run.py / policy_engine.py.
```
