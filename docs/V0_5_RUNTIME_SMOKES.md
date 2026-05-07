# v0.5 Runtime Smokes

This document records local Pi runtime smoke evidence on top of the committed
v0.5 Pi integration contracts.

It is local runtime evidence, not automated CI evidence.

## Status

Committed repo state:

```text
v0.5 = Pi Integration Contracts
```

Local smoke-tested state:

```text
v0.5.1 = verifier-reviewer read-only smoke PASS
v0.5.2 = goal-orchestrator read-only status-report smoke PASS
v0.5.3 = goal-orchestrator disposable certifier-invocation smoke PASS
```

## v0.5.1 verifier-reviewer read-only smoke

Result:

```text
PASS
```

What it validated:

```text
Pi can discover verifier-reviewer.
verifier-reviewer can read existing certifier artifacts.
verifier-reviewer reports status from policy_decision.json.
verifier-reviewer says it cannot certify DONE.
```

Boundary:

```text
Read-only review only.
No file writes.
No status upgrade.
No final_status.md edit.
```

## v0.5.2 goal-orchestrator status-report smoke

Result:

```text
PASS
```

What it validated:

```text
goal-orchestrator can read final_status.md.
goal-orchestrator can read certification.json.
goal-orchestrator can read policy_decision.json.
goal-orchestrator reports status from certifier artifacts only.
```

Boundary:

```text
Read-only status reporting only.
No bash used.
No file writes.
No status artifact changed.
```

## v0.5.3 goal-orchestrator certifier-invocation smoke

Result:

```text
PASS
```

What it validated:

```text
goal-orchestrator can use a disposable copied run.
goal-orchestrator can invoke certify_run.py on that disposable run.
certify_run.py writes final_status.md, certification.json, and policy_decision.json.
goal-orchestrator reports the certifier outputs.
```

Boundary:

```text
Disposable run only.
Original diagnostic run unchanged.
No manual edit to final_status.md.
No manual edit to certification.json.
No manual edit to policy_decision.json.
```

## Caveats

These smokes do not prove full Pi runtime safety.

Not validated yet:

```text
full goal-runner.chain.md runtime
live worker execution
automatic rough-goal compilation
full goal creation
repair behavior
multi-planning
memory behavior
```

Known runtime lesson:

```text
Long complex Pi prompts are fragile.
Short strict one-action prompts work better.
```

The v0.5.3 smoke required bash, so goal-orchestrator bash remains risk. The
allowed command surface is documented in `PI_BASH_ALLOWLIST.md`, but it is not
yet enforced by deterministic runtime code.

## Safe claim

The safe claim after v0.5.3 is:

```text
Pi can discover the contract agents, run read-only status/review smokes, and
invoke the deterministic certifier on a disposable run.
```

The safe claim is not:

```text
Pi can safely run the full goal-runner chain autonomously.
```

