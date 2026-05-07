# Mercury Goal Runner Harness

This harness controls Mercury V2 as a fast worker inside a verified goal-execution system.

The goal is not to make Mercury V2 magically smarter by looping. The goal is to place Mercury V2 inside a controlled harness where every goal becomes a contract, every step produces evidence, and final success is certified by deterministic checks.

## Current status

v1.3 is the deterministic Strategy Planner proof on top of the v1.2 planning handoff proof.

The current research direction is:

```text
Verifier-Provenance Goal Runner Harness
```

The new core question is:

```text
Who is allowed to certify DONE?
```

The latest local benchmark report is:

```text
benchmark_outputs/benchmark_report.md
```

Current benchmark scoring checks the expected verdict for each goal, not just whether the model says `DONE_PASS`. The impossible goal is expected to fail honestly.

See [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for the proof summary and current limitations.
See [`FRAMEWORK.md`](FRAMEWORK.md) for the conceptual architecture and actual current file map.
See [`PROBLEM_AND_GAP.md`](PROBLEM_AND_GAP.md) for the current research problem statement.
See [`VERIFIER_PROVENANCE_DESIGN.md`](VERIFIER_PROVENANCE_DESIGN.md) for the verifier provenance model.
See [`docs/V0_2_1_FREEZE.md`](docs/V0_2_1_FREEZE.md) for the exact freeze boundary.
See [`docs/V0_3_PLANGRAPH.md`](docs/V0_3_PLANGRAPH.md) for the PlanGraph prototype boundary.
See [`docs/V0_3_2_PROVENANCE_GATE_FREEZE.md`](docs/V0_3_2_PROVENANCE_GATE_FREEZE.md) for the provenance runtime gate boundary.
See [`docs/V0_3_3_PROVENANCE_GATE_DIAGNOSTICS.md`](docs/V0_3_3_PROVENANCE_GATE_DIAGNOSTICS.md) for the provenance diagnostic fixture boundary.
See [`docs/V0_3_4_SMELL_SCANNER.md`](docs/V0_3_4_SMELL_SCANNER.md) for the metadata-level verifier smell scanner boundary.
See [`docs/V0_3_5_STRENGTH_SCORER.md`](docs/V0_3_5_STRENGTH_SCORER.md) for the verifier strength scoring boundary.
See [`docs/V0_3_6_POLICY_ENGINE.md`](docs/V0_3_6_POLICY_ENGINE.md) for the deterministic policy engine boundary.
See [`docs/V0_4_DIAGNOSTIC_EVALUATION.md`](docs/V0_4_DIAGNOSTIC_EVALUATION.md) for the small diagnostic evaluation boundary.
See [`docs/V0_5_PI_INTEGRATION.md`](docs/V0_5_PI_INTEGRATION.md) for the Pi integration contract boundary.
See [`docs/V0_5_RUNTIME_SMOKES.md`](docs/V0_5_RUNTIME_SMOKES.md) for the local Pi runtime smoke boundary.
See [`docs/V0_5_7_CONTROLLED_MINI_CHAIN_SMOKE.md`](docs/V0_5_7_CONTROLLED_MINI_CHAIN_SMOKE.md) for the controlled mini-chain smoke boundary.
See [`docs/V0_5_8_PI_CLEAN_EXIT_SMOKE.md`](docs/V0_5_8_PI_CLEAN_EXIT_SMOKE.md) for the Pi clean-exit isolation boundary.
See [`docs/V0_5_9_PI_COMMAND_DISCIPLINE_GATE.md`](docs/V0_5_9_PI_COMMAND_DISCIPLINE_GATE.md) for the Pi command-discipline audit boundary.
See [`docs/V0_5_10_DISPOSABLE_SMOKE_HARNESS.md`](docs/V0_5_10_DISPOSABLE_SMOKE_HARNESS.md) for the disposable Pi smoke setup boundary.
See [`docs/V0_5_11_NEGATIVE_STATUS_SAFETY_SMOKE.md`](docs/V0_5_11_NEGATIVE_STATUS_SAFETY_SMOKE.md) for the negative-status Pi safety boundary.
See [`docs/V0_6_LOCAL_CODING_AGENT_HOST_INTEGRATION.md`](docs/V0_6_LOCAL_CODING_AGENT_HOST_INTEGRATION.md) for the local host integration boundary.
See [`docs/V0_7_BRANCH_GENERATION.md`](docs/V0_7_BRANCH_GENERATION.md) for the branch-generation boundary.
See [`docs/V0_8_EVIDENCE_BRANCH_SELECTION.md`](docs/V0_8_EVIDENCE_BRANCH_SELECTION.md) for the evidence-seeking branch selection boundary.
See [`docs/V0_9_REPLAY_ROLLBACK_AUDIT.md`](docs/V0_9_REPLAY_ROLLBACK_AUDIT.md) for the replay / rollback / audit boundary.
See [`docs/V1_0_PRACTICAL_PACKAGE_FREEZE.md`](docs/V1_0_PRACTICAL_PACKAGE_FREEZE.md) for the practical package freeze boundary.
See [`docs/V1_0_EXAMPLES.md`](docs/V1_0_EXAMPLES.md) for the frozen example set.
See [`docs/V1_1_RAW_GOAL_CHAIN_PROOF.md`](docs/V1_1_RAW_GOAL_CHAIN_PROOF.md) for the deterministic raw-goal chain proof.
See [`docs/V1_2_PLANNING_PROOF_HARDENING.md`](docs/V1_2_PLANNING_PROOF_HARDENING.md) for the deterministic planning handoff proof.
See [`docs/V1_3_STRATEGY_PLANNER.md`](docs/V1_3_STRATEGY_PLANNER.md) for the deterministic strategy-planner proof.
See [`docs/V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md`](docs/V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md) for the v1.4-v2.0 roadmap.
See [`docs/PI_PROMPT_CONTRACTS.md`](docs/PI_PROMPT_CONTRACTS.md) for safe Pi prompt patterns.
See [`docs/PI_BASH_ALLOWLIST.md`](docs/PI_BASH_ALLOWLIST.md) for the current documented bash safety boundary.

The current proof path is:

```text
python -m unittest discover tests -v
python .agentic-pi\diagnostics\evaluation\run_diagnostic_evaluation.py
python .agentic-pi\benchmark\run_benchmark.py
python .agentic-pi\runtime\pi_cli.py --help
```

It demonstrates:

1. a Goal Contract was created,
2. the planner writes plans only,
3. the Guarded Worker writes artifacts inside the active run folder,
4. false pass evidence is rejected,
5. final output paths must match the contract exactly,
6. `artifact_tests` run executable checks for behavior claims,
7. `plan_graph.json`, `artifact_registry.json`, and `task_graph.json` are generated for normal runs,
8. downstream tasks require exact artifact IDs from upstream tasks,
9. provenance-mode runs can return `NOT_DONE`, `PROVISIONAL_DONE`, or `CERTIFIED_DONE`,
10. the four-case provenance diagnostic set verifies P0/P1/P2/missing-verifier behavior,
11. verifier smell reports are recorded without changing final status yet,
12. verifier strength reports are recorded,
13. `policy_decision.json` decides provenance-mode final status,
14. the v0.4 diagnostic evaluation compares weak certifier modes with the policy engine,
15. v0.5 adds Pi orchestration contracts where agents cannot certify DONE,
16. local v0.5.1-v0.5.3 Pi smokes validate read-only review/status and disposable certifier invocation,
17. local v0.5.7 validates a controlled verifier-review + certifier-invocation path with a Pi extension exit caveat,
18. local v0.5.8 isolates the stale Pi exit to the broader extension surface,
19. v0.5.9 adds deterministic Pi command-discipline audit fixtures,
20. v0.5.10 adds deterministic disposable Pi smoke setup,
21. v0.5.11 verifies weak/failing statuses are not repaired or upgraded by Pi,
22. v0.6 adds deterministic local host-task certification against disposable runs,
23. v0.7 adds deterministic branch candidates with verifier requirements,
24. v0.8 selects branches by verifier-provenance certifiability,
25. v0.9 adds read-only replay, dry-run rollback, and audit blocking,
26. v1.0 freezes a thin local command surface and practical examples,
27. v1.1 proves deterministic raw-goal compilation into the full harness path,
28. v1.2 proves the selected branch handoff into `merged_plan.json`,
29. v1.3 proves deterministic task-type routing, capability inventory, strategy gating, strategy scoring, and strategy compilation into `merged_plan.json`,
30. and the benchmark reports false-PASS status explicitly.

## Core parts

1. Prompt Compiler  
Converts a rough user goal into a structured Goal Contract.

2. Goal Contract  
Defines the cleaned goal, final outputs, constraints, done criteria, and failure criteria.

3. Guarded Worker  
Executes one approved step at a time and reports evidence.

4. Trace Logger  
Records what happened during the run.

5. Certifier  
Checks evidence, required files, logs, done criteria, artifact tests, PlanGraph links, and verifier provenance before certification. Legacy runs without `verifier_contract.json` still use `DONE_PASS` / `DONE_FAIL`.

6. Artifact-Linked PlanGraph
Links task outputs to exact artifact IDs and validates downstream artifact consumption when graph files exist.

7. Verifier Provenance Gate
When `verifier_contract.json` exists, separates weak/self-generated evidence from certifying evidence.

8. Smell Scanner
Records metadata-level verifier smell reports for strength scoring and later policy enforcement.

9. Strength Scorer
Scores verifier strength as `weak`, `advisory`, `gating`, or `certifying` for later policy enforcement.

10. Policy Engine
Consumes verifier artifacts, smell reports, strength reports, and the verifier contract to decide provenance-mode status.

11. Small Diagnostic Evaluation
Compares file-existence, artifact-test, provenance-gate, and policy-engine certification on six deterministic cases.

12. Pi Integration Contract
Adds Pi agent and chain prompts for orchestration while preserving `certify_run.py` as final authority.

## Core rule

Mercury may propose, plan, execute, and report, but it cannot certify final success.

Evidence beats confidence.

Next provenance rule:

```text
Self-generated post-solution tests cannot certify DONE alone.
```

## Quick validation commands

Validate a Goal Contract:

```cmd
python .agentic-pi\validators\validate_schema.py .agentic-pi\schemas\goal_contract.schema.json .agentic-runs\real_goal_001\goal_contract.json
```

Validate a Worker step log:

```cmd
python .agentic-pi\validators\validate_schema.py .agentic-pi\schemas\step_result.schema.json .agentic-runs\real_goal_001\step_logs\001.json
```

Run certification:

```cmd
python .agentic-pi\validators\certify_run.py .agentic-runs\<run_id>
```

Run the Pi command-discipline audit on a deterministic fixture:

```cmd
python .agentic-pi\runtime\pi_session_audit.py .agentic-pi\diagnostics\pi_command_discipline\cases\positive_one_bash.jsonl --run-id pi_smoke_one_bash_p2_strong
```

Prepare a disposable Pi smoke run:

```cmd
python .agentic-pi\runtime\setup_pi_smoke.py --target-run-id pi_smoke_one_bash_p2_strong --clean
```

Run the local host integration diagnostic:

```cmd
python .agentic-pi\diagnostics\host_integration\run_host_integration_evaluation.py
```

Show the stable local command surface:

```cmd
python .agentic-pi\runtime\pi_cli.py --help
```

Run the deterministic planning proof:

```cmd
python .agentic-pi\runtime\pi_cli.py goal-compile pi_smoke_planning_proof_p2 --goal "Create README.md explaining the harness" --mode planning_p2
python .agentic-pi\runtime\pi_cli.py goal-plan-proof pi_smoke_planning_proof_p2
python .agentic-pi\runtime\pi_cli.py goal-status pi_smoke_planning_proof_p2 --fail-on-missing
```

Run the deterministic strategy proof:

```cmd
python .agentic-pi\runtime\pi_cli.py goal-compile pi_smoke_strategy_proof_p2 --goal "Create README.md explaining the harness" --mode p2
python .agentic-pi\runtime\pi_cli.py goal-strategy-proof pi_smoke_strategy_proof_p2
python .agentic-pi\runtime\pi_cli.py goal-status pi_smoke_strategy_proof_p2 --fail-on-missing
```

Run a disposable sample:

```cmd
python .agentic-pi\runtime\setup_pi_smoke.py --target-run-id pi_smoke_v1_sample --clean
python .agentic-pi\runtime\pi_cli.py goal-certify pi_smoke_v1_sample
python .agentic-pi\runtime\pi_cli.py goal-status pi_smoke_v1_sample
python .agentic-pi\runtime\pi_cli.py goal-audit pi_smoke_v1_sample
python .agentic-pi\runtime\pi_cli.py goal-replay pi_smoke_v1_sample
```

Run the deterministic smoke test:

```cmd
python smoke_v01.py
```

## Artifact tests

Run the artifact and harness regression tests:

```cmd
python -m unittest discover tests -v
```

## Next milestone

Committed repo state:

```text
v1.3 = Strategy Planner
```

Local smoke-tested state:

```text
v0.5.1 = verifier-reviewer read-only smoke PASS
v0.5.2 = goal-orchestrator read-only status-report smoke PASS
v0.5.3 = goal-orchestrator disposable certifier-invocation smoke PASS
v0.5.7 = controlled mini-chain smoke FUNCTIONAL PASS WITH PI EXIT CAVEAT
v0.5.8 = Pi clean-exit isolation CLEAN EXIT PASS WITH COMMAND-COUNT CAVEAT
v0.5.9 = Pi command-discipline audit IMPLEMENTED
v0.5.10 = Disposable Pi smoke setup IMPLEMENTED
v0.5.11 = Negative-status safety audit IMPLEMENTED
v0.6 = Local coding-agent host integration IMPLEMENTED
v0.7 = Branch contract and deterministic branch generation IMPLEMENTED
v0.8 = Evidence-seeking branch selection IMPLEMENTED
v0.9 = Replay / rollback / audit IMPLEMENTED
v1.0 = Practical package freeze IMPLEMENTED
v1.1 = Raw goal chain proof IMPLEMENTED
v1.2 = Planning proof hardening IMPLEMENTED
v1.3 = Strategy planner IMPLEMENTED
```

The v0.5 Pi chain lives at:

```text
.pi/chains/goal-runner.chain.md
```

The new v0.5 Pi agents are:

```text
.pi/agents/goal-orchestrator.md
.pi/agents/verifier-generator.md
.pi/agents/verifier-reviewer.md
```

The full `goal-runner.chain.md` runtime remains unverified. v0.5.8 shows the stale Pi exit disappears under a subagents-only Pi config. v0.5.9 adds deterministic auditing for one-bash-call discipline, including a failing fixture for the duplicate certifier invocation pattern. v0.5.10 adds deterministic disposable smoke setup so Pi prompts can stay single-action. v0.5.11 verifies that weak/failing statuses are reported, not repaired or upgraded. v0.6 adds local host-task certification against disposable runs. v0.7 adds deterministic branch candidates with explicit verifier requirements. v0.8 selects branches by path to verifier-provenance certification. v0.9 adds read-only replay, dry-run rollback, and audit blocking. v1.0 freezes a thin local command surface and practical examples without claiming full Pi autonomy. v1.1 adds deterministic raw-goal compilation fixtures. v1.2 proves that the selected branch can be materialized into `merged_plan.json` before worker execution and certification. v1.3 adds deterministic strategy selection before step compilation. The next milestone is v1.4 milestone planning, then drift-aware replanning, trajectory evaluation, experience memory, domain packs, and strategy search without claiming full Pi autonomy.

## Planner Stub

The current `plan_router.py` is a deterministic stub for testing. See [PLAN_ROUTER.md](PLAN_ROUTER.md) for details. Real planner agents will replace this stub in future versions.
