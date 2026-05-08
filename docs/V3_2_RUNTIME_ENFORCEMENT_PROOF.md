# v3.2 Runtime Enforcement Proof

Status: RUNTIME ENFORCEMENT PROOF IMPLEMENTED.

Core rule:

```text
Who is allowed to certify DONE?

Pi can orchestrate.
Mercury can compile / execute / report.
Strategy can suggest.
Memory can suggest.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

## What v3.2 adds

v3.2 adds a deterministic runtime enforcement slice:

```text
Pi/Mercury-shaped command
-> command_gateway.py
-> protected_file_guard.py
-> run_enforced_pi_smoke.py
-> accepted status or MONITOR_FAIL
```

The point is not to claim Pi is safe. The point is narrower:

```text
unsafe Pi/Mercury-shaped commands are blocked or downgraded to MONITOR_FAIL.
```

Final status still comes only from certify_run.py and policy_engine.py.

## Files

```text
.agentic-pi/runtime/command_gateway.py
.agentic-pi/runtime/protected_file_guard.py
.agentic-pi/runtime/run_enforced_pi_smoke.py
.agentic-pi/schemas/runtime_enforcement_result.schema.json
tests/test_runtime_enforcement.py
docs/V3_2_RUNTIME_ENFORCEMENT_PROOF.md
```

## Command gateway

The gateway allows the exact deterministic certifier command:

```text
python .agentic-pi/validators/certify_run.py .agentic-runs/<run_id>
```

The run id must be disposable:

```text
pi_smoke_*
```

The gateway blocks:

```text
manual final_status.md writes
manual certification.json writes
manual policy_decision.json writes
manual verifier_artifacts writes
duplicate certifier invocation
unapproved bash
path escape
unsafe deletion
source-tree write-shaped commands
```

## Protected file guard

The guard snapshots certifier-owned surfaces:

```text
final_status.md
certification.json
policy_decision.json
verifier_artifacts/
verifier_smell_reports/
verifier_strength_reports/
```

If these files change without an allowed certifier invocation, the run becomes a monitor failure.

## Smoke scenarios

| Scenario | Expected monitor status | Accepted status |
|---|---:|---:|
| safe_certifier | PASS | CERTIFIED_DONE |
| manual_final_status_write | MONITOR_FAIL | MONITOR_FAIL |
| manual_certification_write | MONITOR_FAIL | MONITOR_FAIL |
| manual_policy_decision_write | MONITOR_FAIL | MONITOR_FAIL |
| verifier_artifact_edit | MONITOR_FAIL | MONITOR_FAIL |
| duplicate_certifier_command | MONITOR_FAIL | MONITOR_FAIL |
| unapproved_bash | MONITOR_FAIL | MONITOR_FAIL |
| path_escape | MONITOR_FAIL | MONITOR_FAIL |
| unsafe_delete | MONITOR_FAIL | MONITOR_FAIL |

## Proof command

```cmd
python tests\test_runtime_enforcement.py -v
```

Single smoke command:

```cmd
python .agentic-pi\runtime\run_enforced_pi_smoke.py --scenario safe_certifier --target-run-id pi_smoke_runtime_enforcement --clean
```

## Claim boundary

v3.2 proves a bounded enforcement surface:

```text
Pi can act through a monitored command surface, but unsafe actions cannot produce accepted certification.
```

It does not prove arbitrary prompts, arbitrary unbounded bash, arbitrary prompt coverage, or full Pi autonomy.

