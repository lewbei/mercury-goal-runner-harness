# v1.0 Practical Package Freeze

This document records the v1.0 practical package boundary.

The purpose is usability, not full autonomy.

## Status

```text
PRACTICAL PACKAGE FREEZE IMPLEMENTED
```

## Command surface

The stable command surface is:

```text
goal-init
goal-compile
goal-run
goal-certify
goal-status
goal-replay
goal-audit
goal-rollback
```

The local command entrypoint is:

```cmd
python .agentic-pi\runtime\pi_cli.py --help
```

The optional installed entrypoint is:

```cmd
mercury-goal --help
```

The console entrypoint is intentionally thin. It dispatches to deterministic
harness tools. It does not certify DONE itself.

## Examples

The frozen example set is:

```text
docs/V1_0_EXAMPLES.md
```

The examples cover:

```text
legacy DONE_PASS
PROVISIONAL_DONE provenance mode
CERTIFIED_DONE provenance mode
false-PASS rejection
```

## Safeguards

Final status remains owned by:

```text
certify_run.py
policy_engine.py
```

Support tools may write their own reports:

```text
audit_report.json
run_manifest.json
replay_report.json
rollback_report.json
```

Support tools cannot certify DONE by themselves.

Rollback is dry-run by default. `--apply` is required for mutation, and rollback
is limited to run-folder-owned artifacts with valid backup provenance.

## Safe claim

Safe claim:

```text
A local user can run the stable harness commands for init, prepared-run
execution, certification, status, replay, audit, and rollback dry-run.
```

Unsafe claim:

```text
The full Pi goal-runner chain is autonomously verified.
```

That remains false.

## Proof commands

```cmd
python tests\test_v1_package_freeze.py -v
python -m unittest discover tests -v
python .agentic-pi\diagnostics\evaluation\run_diagnostic_evaluation.py
python .agentic-pi\benchmark\run_benchmark.py
python .agentic-pi\runtime\pi_cli.py --help
```
