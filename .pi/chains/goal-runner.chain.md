# Goal Runner Chain

This chain integrates Pi with the Verifier-Provenance Goal Runner Harness.

It is an orchestration contract, not a new certification mechanism.

## Authority Rule

```text
Pi can orchestrate.
Mercury can compile/execute/report.
Verifier agents can propose evidence.
certify_run.py + policy_engine.py decide final status.
```

No Pi agent may certify DONE.

## Steps

1. `goal-orchestrator` receives the user goal and identifies the run folder.
2. `prompt-compiler` creates or reviews `goal_contract.json`.
3. `verifier-generator` proposes verifier requirements before worker execution.
4. `guarded-worker` executes approved worker steps inside `.agentic-runs/<run_id>/`.
5. `verifier-reviewer` reviews verifier artifacts, smell reports, strength reports, and policy risk.
6. `goal-orchestrator` invokes the deterministic certifier:

```cmd
python .agentic-pi/validators/certify_run.py .agentic-runs/<run_id>
```

7. `goal-orchestrator` reports only the status written by the certifier:

```text
final_status.md
certification.json
policy_decision.json
```

## Outputs

The chain may report:

- run folder path,
- goal contract path,
- verifier contract path,
- verifier artifact paths,
- certification command,
- final status from certifier output.

The chain must not produce its own final status.

## Memory Boundary

The chain may read a prepared `.agentic-runs/<run_id>/context_pack.json` when it already exists. That context pack is advisory only and must contain `can_certify_done: false`. The chain must not read or write removed flat memory stores and must not promote durable memory directly.

## Deferred

This chain does not add:

- direct durable-memory promotion,
- new PlanGraph features,
- real Mercury planner changes,
- SWE-bench integration,
- OpenHands integration,
- broad benchmark expansion.
