# v0.5.8 Pi Clean-Exit Smoke

This document records the v0.5.8 Pi clean-exit isolation smoke.

It is local runtime evidence, not automated CI evidence.

## Status

```text
CLEAN EXIT PASS WITH COMMAND-COUNT CAVEAT
```

What passed:

```text
The same disposable P2-strong run certified as CERTIFIED_DONE.
An isolated Pi config with only pi-subagents exited with code 0.
The stale @tmustier/pi-agent-teams extension-context crash disappeared.
The original diagnostic source run hashes were unchanged.
```

What remains imperfect:

```text
In the clean isolated subagent run, goal-orchestrator invoked the deterministic
certifier twice: once with backslash paths and once with forward-slash paths.
Both invocations targeted the same disposable run and the same certifier.
```

So v0.5.8 proves the stale exit is extension-surface related, but it does not
yet prove one-bash-call discipline.

## Compared Pi surfaces

Current global Pi package surface:

```text
npm:@ollama/pi-web-search
npm:pi-mcp-adapter
npm:@tmustier/pi-agent-teams
npm:@tintinweb/pi-tasks
npm:pi-teams
npm:pi-subagents
npm:@tintinweb/pi-subagents
npm:pi-supervisor
```

Observed result:

```text
certifier artifacts: CERTIFIED_DONE
Pi process exit: 1
error source: @tmustier/pi-agent-teams stale extension context
```

Temporary isolated Pi config:

```text
PI_CODING_AGENT_DIR=.agentic-runs/pi_smoke_clean_exit_config
packages=[npm:pi-subagents]
defaultProvider=openrouter
defaultModel=inception/mercury-2
```

Observed result:

```text
certifier artifacts: CERTIFIED_DONE
Pi process exit: 0
stale extension-context error: not reproduced
```

## Run folders

Source run:

```text
.agentic-runs/diagnostic_eval_p2_strong
```

Disposable smoke run:

```text
.agentic-runs/pi_smoke_clean_exit_p2_strong
```

Temporary Pi config:

```text
.agentic-runs/pi_smoke_clean_exit_config
```

Both disposable paths are ignored by git through:

```text
.agentic-runs/pi_smoke_*/
```

## Source-run hash check

The original diagnostic source status artifacts remained unchanged after the
smoke:

```text
CB91DC368FA9A3728785C3A0D10A59B8054EACB5C12C106B921418729B26E716  final_status.md
657847DBB2313AE00E401DABB4B41EB97FA112AA803D876DD6AAAB3DFBD93EF8  certification.json
4CDAF83F76D953933AA8B49016D3DE0B82CFC063D3155CC93511F39CB7A34471  policy_decision.json
```

## Passing isolated prompt

```text
Use goal-orchestrator only.
Run only this command:
python .agentic-pi\validators\certify_run.py .agentic-runs\pi_smoke_clean_exit_p2_strong

Then read exactly these files:
.agentic-runs/pi_smoke_clean_exit_p2_strong/final_status.md
.agentic-runs/pi_smoke_clean_exit_p2_strong/certification.json
.agentic-runs/pi_smoke_clean_exit_p2_strong/policy_decision.json

Report the status from each file. Do not run any other bash command. Do not edit files manually. Do not certify DONE yourself. Final status comes only from certify_run.py.
```

Observed output:

```text
final_status.md: CERTIFIED_DONE
certification.json: CERTIFIED_DONE
policy_decision.json: CERTIFIED_DONE
```

Generated timestamps:

```text
certification.json timestamp: 2026-05-07T04:29:26.431665+00:00
policy_decision.json generated_at: 2026-05-07T04:29:26.417833+00:00
```

Session evidence:

```text
session: .agentic-runs/pi_smoke_clean_exit_config/sessions/--C--Users-lewka-deep_learning-mercury-goal-runner-harness--/2026-05-07T04-29-13-687Z_019e00b2-6c56-7508-9221-afdc15f2154a.jsonl
subagent artifact: a19bf755_goal-orchestrator_0_output.md
subagent meta: a19bf755_goal-orchestrator_0_meta.json
agent: goal-orchestrator
model: inception/mercury-2:high
subagent exit code: 0
parent Pi process exit code: 0
tool count: 5
```

Tool-call caveat:

```text
goal-orchestrator ran certify_run.py twice on the same disposable run:
1. python .agentic-pi\validators\certify_run.py .agentic-runs\pi_smoke_clean_exit_p2_strong
2. python .agentic-pi/validators/certify_run.py .agentic-runs/pi_smoke_clean_exit_p2_strong
```

The second invocation appears to be path-normalization behavior. This should be
fixed before claiming strict one-command orchestration.

## Non-counted stricter retry

A stricter prompt was also tested under the isolated config. It exited with code
0 and produced `CERTIFIED_DONE`, but it is not counted as the mini-chain proof
because the parent Pi session used direct bash instead of launching
`goal-orchestrator`, and it retried after a backslash path failure.

This reinforces the v0.5 prompt-contract rule:

```text
Short prompts help, but deterministic command discipline still needs runtime enforcement.
```

## Safe claim

Safe claim:

```text
The stale Pi process exit is caused by the broader installed extension surface.
Under an isolated subagents-only Pi config, the controlled certifier invocation
path exits cleanly while preserving verifier-provenance authority.
```

Still not proven:

```text
one-bash-call enforcement
full goal-runner.chain.md runtime
live worker execution
automatic rough-goal compilation
repair behavior
clean runtime with all globally installed Pi extensions enabled
```

Final status still comes only from:

```text
certify_run.py
policy_engine.py
```

