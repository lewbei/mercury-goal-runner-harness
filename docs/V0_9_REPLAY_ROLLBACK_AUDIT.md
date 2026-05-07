# v0.9 Replay / Rollback / Audit

This document records the v0.9 replay, rollback, and audit slice.

It makes run history more inspectable. It does not let audit evidence certify
DONE by itself.

## Status

```text
REPLAY ROLLBACK AUDIT IMPLEMENTED
```

## Rule

```text
Replay is read-only.
Rollback is dry-run by default.
Audit can block certification.
Audit cannot certify DONE by itself.
```

Final status still comes only from:

```text
certify_run.py
policy_engine.py
```

## Runtime tools

```text
.agentic-pi/runtime/audit_run.py
.agentic-pi/runtime/replay_run.py
.agentic-pi/runtime/rollback_run.py
```

They write:

```text
run_manifest.json
audit_report.json
replay_report.json
rollback_report.json
```

The schema boundary is:

```text
.agentic-pi/schemas/run_manifest.schema.json
.agentic-pi/schemas/audit_report.schema.json
.agentic-pi/schemas/replay_report.schema.json
.agentic-pi/schemas/rollback_report.schema.json
.agentic-pi/schemas/backup_manifest.schema.json
```

## Certification integration

If `audit_report.json` exists and says:

```json
{ "valid": false }
```

then certification is blocked:

```text
legacy mode -> DONE_FAIL
provenance mode -> NOT_DONE
```

If the audit report is valid, it is a passed check. It still does not certify
DONE.

## Rollback boundary

Rollback requires backup provenance:

```text
target_path
backup_path
original_hash
backup_hash
creator
timestamp
phase
reason
```

Rollback rejects:

```text
absolute paths
path traversal
final_status.md
certification.json
policy_decision.json
verifier_artifacts/
missing backup manifests
backup hash mismatch
```

Rollback applies only with:

```text
--apply
```

Without `--apply`, rollback is dry-run.

## Safe claim

Safe claim:

```text
The harness can audit and replay run state, and can dry-run or apply rollback
inside a run folder only when backup provenance matches.
```

Replay checks `run_manifest.json` when it exists, including trace count, step log
count, provenance mode, and recorded artifact hashes. Replay still does not
certify DONE.

Unsafe claim:

```text
Replay or audit proves DONE.
```

That remains false.

## Proof commands

```cmd
python tests\test_replay_audit_rollback.py -v
python -m unittest discover tests -v
python .agentic-pi\diagnostics\evaluation\run_diagnostic_evaluation.py
python .agentic-pi\benchmark\run_benchmark.py
```
