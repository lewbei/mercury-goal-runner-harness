# v1.0 Examples

These examples are the practical package examples for the
Verifier-Provenance Goal Runner Harness.

They are examples of certification behavior, not proof that Pi or Mercury can
solve arbitrary goals autonomously.

## Legacy DONE_PASS

Legacy runs without `verifier_contract.json` still use:

```text
DONE_PASS
DONE_FAIL
```

Use the benchmark simple/medium/hard cases as the legacy examples. These remain
legacy-compatible because no verifier contract is required.

## PROVISIONAL_DONE

`PROVISIONAL_DONE` means the target artifact can exist and local evidence can
pass, but the verifier authority is not enough for final certification.

Reference fixture:

```text
.agentic-pi/diagnostics/evaluation/cases/p1_visible_only
```

Expected policy-engine status:

```text
PROVISIONAL_DONE
```

## CERTIFIED_DONE

`CERTIFIED_DONE` requires certifying verifier authority and certifying strength.

Reference fixture:

```text
.agentic-pi/diagnostics/evaluation/cases/p2_strong
```

Expected policy-engine status:

```text
CERTIFIED_DONE
```

## False-PASS Rejection

A file existing is not enough.

Reference fixture:

```text
.agentic-pi/diagnostics/evaluation/cases/file_exists_but_wrong
```

Expected policy-engine status:

```text
NOT_DONE
```

## Run A Sample

Prepare a disposable sample from the strong P2 fixture:

```cmd
python .agentic-pi\runtime\setup_pi_smoke.py --target-run-id pi_smoke_v1_sample --clean
python .agentic-pi\runtime\pi_cli.py goal-certify pi_smoke_v1_sample
python .agentic-pi\runtime\pi_cli.py goal-status pi_smoke_v1_sample
python .agentic-pi\runtime\pi_cli.py goal-audit pi_smoke_v1_sample
python .agentic-pi\runtime\pi_cli.py goal-replay pi_smoke_v1_sample
```

Final status still comes only from:

```text
certify_run.py
policy_engine.py
```
