# v1.4 Milestone Planning

## MILESTONE PLANNING IMPLEMENTED

v1.4 adds a deterministic milestone layer between selected strategy and executable local steps.

The invariant stays unchanged:

```text
Who is allowed to certify DONE?
Strategy can suggest.
Planner can select.
Milestones can guide.
Worker can execute.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

## Proof Path

The implemented path is:

```text
raw goal
  -> task type
  -> capability inventory
  -> strategy candidates
  -> applicability gate
  -> strategy score
  -> selected strategy
  -> milestone_plan.json
  -> milestone_status.json
  -> local_step_plan.json
  -> step compiler
  -> merged_plan.json
  -> worker
  -> certifier
```

The CLI command is:

```cmd
python .agentic-pi\runtime\pi_cli.py goal-milestone-proof <run_id>
```

It expects an existing run folder with `goal_contract.json` and optional `verifier_contract.json`.

## Implemented Files

```text
.agentic-pi/runtime/milestone_builder.py
.agentic-pi/runtime/milestone_tracker.py
.agentic-pi/runtime/local_step_planner.py
.agentic-pi/runtime/milestone_proof_runner.py
```

Updated:

```text
.agentic-pi/runtime/step_compiler.py
.agentic-pi/runtime/pi_cli.py
```

Schemas:

```text
.agentic-pi/schemas/milestone_plan.schema.json
.agentic-pi/schemas/milestone_status.schema.json
.agentic-pi/schemas/local_step_plan.schema.json
```

## Milestone Types

Coding:

```text
reproduce/inspect
patch
verify
certify
```

Research:

```text
define claim
collect closest sources
build comparison matrix
attack novelty
final verdict
```

Writing:

```text
outline
draft
verify constraints
finalize
```

Debugging:

```text
reproduce
inspect
patch
regression verify
certify
```

Benchmark:

```text
define expected
run diagnostic
compare
false pass check
certify
```

Experiment:

```text
define protocol
prepare artifacts
check results
certify
```

## Status Boundary

Milestone statuses are local planning statuses only:

```text
planned
active
complete
blocked
```

They are not final certification statuses.

Milestone artifacts cannot write or replace:

```text
final_status.md
certification.json
policy_decision.json
```

## Step Compiler Behavior

`step_compiler.py` now has two paths:

```text
local_step_plan.json exists -> compile local milestone steps into merged_plan.json
local_step_plan.json missing -> legacy v1.3 strategy-only compile path
```

This keeps v1.3 compatible while proving v1.4 separately.

## What This Proves

v1.4 proves:

```text
selected strategies can be expanded into deterministic milestone plans
milestone statuses are recorded without final authority
milestones can be lowered into executable local steps
local steps preserve milestone order
step_compiler.py consumes local_step_plan.json when present
the milestone-derived merged plan can execute through the worker
the certifier still writes the final status
```

## What This Does Not Prove

v1.4 does not prove:

```text
semantic quality of milestones
live Mercury milestone planning quality
drift-aware replanning
trajectory-level evaluation
experience memory
domain pack quality
strategy search or workflow optimization
full Pi goal-runner.chain.md autonomy
```

## Safe Claim

The safe claim is:

```text
The harness can deterministically expand a selected strategy into milestones, lower those milestones into local executable steps, compile those steps into merged_plan.json, execute them through the worker, and rely on certify_run.py / policy_engine.py for final status.
```

The unsafe claim is:

```text
The harness can autonomously plan long-horizon arbitrary tasks.
```

Do not make the unsafe claim.
