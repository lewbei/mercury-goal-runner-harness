# v0.6 Local Coding-Agent Host Integration

This document records the v0.6 local host integration slice.

It is deterministic local host execution for disposable coding-agent-style
tasks. It is not full Pi autonomy, not real Mercury planning, and not broad
benchmark expansion.

## Status

```text
LOCAL HOST INTEGRATION IMPLEMENTED
```

## Host rule

```text
Host can prepare disposable local runs.
Host can invoke certify_run.py through sys.executable.
Host can read final_status.md, certification.json, and policy_decision.json.
Host cannot certify DONE by text.
```

Final status still comes only from:

```text
certify_run.py
policy_engine.py
```

## Host runner

The runner is:

```text
.agentic-pi/runtime/host_task_runner.py
```

It:

```text
1. loads a host_task.json fixture,
2. copies a known diagnostic source into .agentic-runs/pi_smoke_*,
3. rewrites run_id only inside the copied disposable folder,
4. invokes certify_run.py through sys.executable, not shell text,
5. collects certifier status artifacts,
6. checks source-run hashes before and after,
7. rejects manual status writes, duplicate certifier commands, and source mutation attempts.
```

## Diagnostic cases

Fixtures live under:

```text
.agentic-pi/diagnostics/host_integration/cases/
```

Cases:

```text
read_status_p2_strong -> PASS / CERTIFIED_DONE
certify_p2_strong_once -> PASS / CERTIFIED_DONE
certify_p1_visible_provisional -> PASS / PROVISIONAL_DONE
reject_manual_status_write -> FAIL
reject_double_certifier_command -> FAIL
reject_source_run_mutation -> FAIL
```

The evaluation runner is:

```text
.agentic-pi/diagnostics/host_integration/run_host_integration_evaluation.py
```

## Safe claim

Safe claim:

```text
The harness can run deterministic local host-task certification against
disposable run folders and reject host-side false certification risks.
```

Unsafe claim:

```text
The full Pi chain can autonomously create, repair, and certify coding tasks.
```

That remains unverified.

## Proof commands

```cmd
python tests\test_host_task_runner.py -v
python tests\test_host_integration_evaluation.py -v
python .agentic-pi\diagnostics\host_integration\run_host_integration_evaluation.py
python -m unittest discover tests -v
python .agentic-pi\diagnostics\evaluation\run_diagnostic_evaluation.py
python .agentic-pi\benchmark\run_benchmark.py
```
