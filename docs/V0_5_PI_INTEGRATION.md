# v0.5 Pi Integration

v0.5 adds a Pi orchestration contract on top of the v0.4 Small Diagnostic Evaluation.

The goal is:

```text
Integrate the harness into Pi as an orchestrated workflow,
but keep deterministic certifier/policy engine as final authority.
```

## Added Files

```text
.pi/agents/goal-orchestrator.md
.pi/agents/verifier-generator.md
.pi/agents/verifier-reviewer.md
.pi/chains/goal-runner.chain.md
tests/test_pi_integration_contracts.py
```

## Authority Rule

```text
Pi can orchestrate.
Mercury can compile/execute/report.
Verifier agents can propose evidence.
certify_run.py + policy_engine.py decide final status.
```

## What v0.5 Adds

- discoverable Pi agent prompt contracts,
- a goal-runner chain contract,
- explicit permission boundaries,
- explicit `cannot certify DONE` language for each new agent,
- tests that check the final status still comes only from `certify_run.py`.

## What v0.5 Does Not Add

- new research mechanisms,
- memory behavior,
- new PlanGraph features,
- real Mercury planner changes,
- SWE-bench,
- OpenHands,
- broad benchmark expansion,
- agent-issued final status.

## Acceptance

```cmd
python tests\test_pi_integration_contracts.py -v
python -m unittest discover tests -v
python .agentic-pi\diagnostics\evaluation\run_diagnostic_evaluation.py
python .agentic-pi\benchmark\run_benchmark.py
```

Expected:

```text
Pi agent files exist and are discoverable.
Each Pi agent has narrow permissions.
Agent prompts say they cannot certify DONE.
Final status still comes only from certify_run.py.
Existing tests still pass.
```
