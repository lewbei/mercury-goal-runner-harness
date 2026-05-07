# v1.5 Drift-Aware Replanning

## DRIFT-AWARE REPLANNING IMPLEMENTED

v1.5 adds deterministic drift detection after worker execution and before certification.

The invariant stays unchanged:

```text
Who is allowed to certify DONE?
Strategy can suggest.
Planner can select.
Milestones can guide.
Drift reports can block.
Delta plans can suggest repair.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

## Proof Path

The implemented path is:

```text
raw goal
  -> selected strategy
  -> milestone_plan.json
  -> local_step_plan.json
  -> merged_plan.json
  -> worker
  -> checkpoints/
  -> plan_monitor_report.json
  -> drift_report.json
  -> delta_plan.json
  -> delta_plan_validation.json
  -> certifier
```

The CLI command is:

```cmd
python .agentic-pi\runtime\pi_cli.py goal-drift-proof <run_id>
```

## Implemented Files

```text
.agentic-pi/runtime/checkpoint_writer.py
.agentic-pi/runtime/plan_monitor.py
.agentic-pi/runtime/drift_detector.py
.agentic-pi/runtime/replan_controller.py
.agentic-pi/runtime/drift_proof_runner.py
.agentic-pi/validators/validate_delta_plan.py
```

Updated:

```text
.agentic-pi/validators/certify_run.py
.agentic-pi/runtime/pi_cli.py
```

Schemas:

```text
.agentic-pi/schemas/checkpoint.schema.json
.agentic-pi/schemas/drift_report.schema.json
.agentic-pi/schemas/delta_plan.schema.json
```

## Drift Levels

```text
none       = execution matches the approved plan
minor      = non-blocking note
repairable = local delta plan may recreate expected artifacts
fatal      = unsafe drift; abort and require user review
```

## Fatal Drift

Fatal drift includes:

```text
worker touches final_status.md
worker touches certification.json
worker touches policy_decision.json
worker touches verifier_artifacts/
worker touches verifier_smell_reports/
worker touches verifier_strength_reports/
path escapes the run folder
malformed step log that cannot be trusted
```

Fatal drift produces:

```text
drift_level = fatal
delta_plan decision_status = ABORT_REQUIRES_USER
```

## Repairable Drift

Repairable drift includes:

```text
wrong artifact path touched
expected artifact missing
step count mismatch
action mismatch
```

Repairable drift produces:

```text
drift_level = repairable
delta_plan decision_status = DELTA_PLAN_CREATED
```

The delta plan is still only a repair suggestion. It cannot certify DONE.

## Certifier Gate

`certify_run.py` now checks `drift_report.json` when present.

Allowed:

```text
drift_level = none
drift_level = minor
```

Blocking:

```text
invalid drift_report.json
drift_level = repairable
drift_level = fatal
blocking = true
```

In provenance mode, blocking drift returns:

```text
NOT_DONE
```

In legacy mode, blocking drift returns:

```text
DONE_FAIL
```

## What This Proves

v1.5 proves:

```text
checkpoints can be written after worker execution
execution can be compared to merged_plan.json
wrong artifact paths are repairable drift
protected status/provenance writes are fatal drift
repairable drift can create a bounded delta_plan.json
unsafe delta plans are rejected
blocking drift prevents certification
```

## What This Does Not Prove

v1.5 does not prove:

```text
automatic safe repair application
full rollback application
live Mercury replanning quality
trajectory-level evaluation
experience memory
domain pack quality
strategy search or workflow optimization
full Pi goal-runner.chain.md autonomy
```

## Safe Claim

The safe claim is:

```text
The harness can detect drift from the approved plan, classify it as none/minor/repairable/fatal, generate a bounded delta plan for repairable drift, reject unsafe delta plans, and block certification when drift is unresolved.
```

The unsafe claim is:

```text
The harness can automatically repair arbitrary failed runs.
```

Do not make the unsafe claim.
