# v0.5.7 Controlled Mini-Chain Smoke

This document records the v0.5.7 local Pi runtime smoke.

It is local runtime evidence, not automated CI evidence.

## Status

```text
FUNCTIONAL PASS WITH PI EXIT CAVEAT
```

What passed:

```text
verifier-reviewer read the disposable run artifacts with read-only tools.
goal-orchestrator invoked the deterministic certifier through the Agent tool.
certify_run.py regenerated final_status.md, certification.json, and policy_decision.json.
All three certifier artifacts reported CERTIFIED_DONE.
The original diagnostic source run hashes were unchanged.
```

What did not fully pass:

```text
The Pi process exited with code 1 after producing the expected output because
the installed pi-agent-teams extension raised a stale extension context error.
```

So this is not a clean full Pi process-level pass.

## Run folders

Source run:

```text
.agentic-runs/diagnostic_eval_p2_strong
```

Disposable smoke run:

```text
.agentic-runs/pi_smoke_mini_chain_p2_strong
```

The disposable folder is ignored by git through:

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

## Prompt 1: verifier-reviewer

Passing prompt:

```text
Use verifier-reviewer only.
Read these four files in .agentic-runs/pi_smoke_mini_chain_p2_strong:
verifier_artifacts/V.P2_STRONG.json
verifier_strength_reports/V.P2_STRONG.json
policy_decision.json
final_status.md
Report provenance_level, strength_level, policy status, final status, and say you cannot certify DONE. Do not write files.
```

Observed result:

```text
Provenance level: P2
Strength level: certifying
Policy status: CERTIFIED_DONE
Final status: CERTIFIED_DONE
I am not authorized to certify DONE.
```

Session evidence:

```text
session: C:\Users\lewka\.pi\agent\sessions\--C--Users-lewka-deep_learning-mercury-goal-runner-harness--\2026-05-07T04-14-53-045Z_019e00a5-4a74-74ee-97e9-63e2cb6cf3ab.jsonl
subagent output: C:\Users\lewka\.pi\agent\sessions\--C--Users-lewka-deep_learning-mercury-goal-runner-harness--\subagent-artifacts\f81a7f95_verifier-reviewer_0_output.md
model: inception/mercury-2:high
tool count: 4
tools used: read only
```

## Prompt 2: goal-orchestrator

Before this prompt, generated certifier outputs were removed only from the
disposable run:

```text
final_status.md
certification.json
policy_decision.json
verifier_smell_reports/
verifier_strength_reports/
```

Passing prompt:

```text
Use goal-orchestrator only.
Run only this command:
python .agentic-pi\validators\certify_run.py .agentic-runs\pi_smoke_mini_chain_p2_strong

Then read exactly these files:
.agentic-runs/pi_smoke_mini_chain_p2_strong/final_status.md
.agentic-runs/pi_smoke_mini_chain_p2_strong/certification.json
.agentic-runs/pi_smoke_mini_chain_p2_strong/policy_decision.json

Report the status from each file. Do not run any other bash command. Do not edit files manually. Do not certify DONE yourself. Final status comes only from certify_run.py.
```

Observed result:

```text
goal-orchestrator completed through the Agent tool.
goal-orchestrator tool uses: 2.
certify_run.py regenerated the certifier artifacts.
final_status.md status: CERTIFIED_DONE
certification.json status: CERTIFIED_DONE
policy_decision.json status: CERTIFIED_DONE
```

Generated timestamps:

```text
certification.json timestamp: 2026-05-07T04:18:13.609354+00:00
policy_decision.json generated_at: 2026-05-07T04:18:13.585980+00:00
```

Session evidence:

```text
session: C:\Users\lewka\.pi\agent\sessions\--C--Users-lewka-deep_learning-mercury-goal-runner-harness--\2026-05-07T04-17-57-576Z_019e00a8-1b47-77a9-81ca-c6f1e128cf2f.jsonl
model: inception/mercury-2
Agent subagent_type: goal-orchestrator
Agent result: completed
```

## Caveat: Pi extension exit error

After the goal-orchestrator output was produced, the Pi process exited with:

```text
Error: This extension ctx is stale after session replacement or reload.
heartbeatActiveAttachClaim
@tmustier/pi-agent-teams
```

This happened after the certifier artifacts were generated and read. It appears
to be a Pi extension lifecycle issue, not a certifier or policy-engine failure.

The safe status is therefore:

```text
controlled mini-chain path: functional pass
Pi process cleanliness: fail due to extension stale-context error
```

## Safe claim

Safe claim:

```text
Pi can run a controlled verifier-review + certifier-invocation path on a disposable run.
```

Still not proven:

```text
full goal-runner.chain.md runtime
live worker execution
automatic rough-goal compilation
repair behavior
Pi process-level cleanliness with all installed extensions enabled
```

Final status still comes only from:

```text
certify_run.py
policy_engine.py
```

