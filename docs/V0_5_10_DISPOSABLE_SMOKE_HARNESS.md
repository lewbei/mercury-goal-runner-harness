# v0.5.10 Disposable Smoke Harness

This document records the v0.5.10 disposable smoke setup slice.

It is local deterministic setup for Pi smoke runs. It is not host integration,
not full Pi chain execution, and not live worker execution.

## Status

```text
DISPOSABLE SMOKE SETUP IMPLEMENTED
```

v0.5.10 exists to remove setup work from Pi prompts.

The prompt contract stays:

```text
One prompt = one action.
Pi should certify/report only.
No copy + repair + certify + summarize prompt.
```

## Setup utility

The setup utility is:

```text
.agentic-pi/runtime/setup_pi_smoke.py
```

It copies a known diagnostic source run into a disposable run folder:

```text
.agentic-runs/pi_smoke_*
```

It then:

```text
1. rewrites run_id only inside the copied disposable folder,
2. removes generated certifier outputs only inside the disposable folder,
3. hashes the source before and after,
4. fails if the source diagnostic run changed,
5. prints the single next certifier command Pi may run.
```

## Default source

Default source:

```text
.agentic-pi/diagnostics/evaluation/cases/p2_strong
```

Example setup:

```cmd
python .agentic-pi\runtime\setup_pi_smoke.py --target-run-id pi_smoke_one_bash_p2_strong --clean
```

Expected next Pi command:

```text
python .agentic-pi/validators/certify_run.py .agentic-runs/pi_smoke_one_bash_p2_strong
```

## Safety boundary

Allowed:

```text
copy a diagnostic source into an explicitly named .agentic-runs/pi_smoke_* folder
rewrite run_id inside that copied folder
remove generated certifier outputs inside that copied folder
```

Forbidden:

```text
copy/setup work inside Pi prompt
target run IDs outside pi_smoke_*
source-run mutation
manual edits to final_status.md, certification.json, or policy_decision.json
manual edits to verifier_artifacts/
```

## Safe claim

Safe claim:

```text
The harness can prepare disposable Pi smoke runs deterministically while
preserving source-run hashes and keeping Pi prompts single-action.
```

Unsafe claim:

```text
Pi can autonomously prepare, repair, certify, and summarize a run.
```

That remains unverified and out of scope.

## Proof commands

```cmd
python tests\test_pi_smoke_setup.py -v
python -m unittest discover tests -v
python .agentic-pi\diagnostics\evaluation\run_diagnostic_evaluation.py
python .agentic-pi\benchmark\run_benchmark.py
```

Final status still comes only from:

```text
certify_run.py
policy_engine.py
```
