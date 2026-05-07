# Project Status

## Current version

Mercury Goal Runner Harness v1.2 is Planning Proof Hardening on top of the v1.1 raw-goal chain proof.

The purpose of this repository is not to claim that Mercury V2 becomes smarter by looping. The purpose is to place Mercury V2 inside a controlled goal-execution harness where outputs are checked through contracts, logs, evidence, and certification.

The current research direction has shifted to:

```text
Verifier-Provenance Goal Runner Harness
```

The central question is:

```text
Who is allowed to certify DONE?
```

## Current result

Status: LOCAL PASS

The current harness passes its local regression tests and the current benchmark verdict check:

```text
python -m unittest discover tests -v
python .agentic-pi\diagnostics\evaluation\run_diagnostic_evaluation.py
python .agentic-pi\benchmark\run_benchmark.py
python .agentic-pi\runtime\pi_cli.py --help
```

Latest benchmark summary:

```text
benchmark_outputs/benchmark_report.md
```

The benchmark now scores `actual_status == expected_status`. This matters because the impossible goal should not be counted as a failure when the harness honestly certifies `DONE_FAIL`; it would only be a false PASS if it returned `DONE_PASS`.

The latest benchmark includes five cases:

- simple,
- medium,
- hard executable CLI,
- impossible/risky,
- and long-range artifact dependency.

The provenance gate diagnostic set includes four deterministic cases:

- `case_p0_self_test` -> `PROVISIONAL_DONE`,
- `case_p1_existing_test` -> `PROVISIONAL_DONE`,
- `case_p2_independent_test` -> `CERTIFIED_DONE`,
- `case_missing_verifier` -> `NOT_DONE`.

The v0.3.4 smell scanner records metadata-level verifier smell reports.

The v0.3.5 strength scorer converts verifier metadata and smell reports into `weak`, `advisory`, `gating`, or `certifying` strength reports.

The v0.3.6 policy engine consumes verifier artifacts, smell reports, strength reports, and verifier contracts to decide provenance-mode final status.

The v0.4 diagnostic evaluation compares four certification modes on six deterministic cases:

- file-existence certifier,
- artifact-test certifier,
- provenance-gated certifier,
- and policy-engine certifier.

The main diagnostic metric is:

```text
false CERTIFIED_DONE rate
```

The v0.5 Pi integration adds prompt/chain contracts for:

- `goal-orchestrator`,
- `verifier-generator`,
- `verifier-reviewer`,
- and `goal-runner.chain.md`.

The v0.5 rule remains:

```text
Pi can orchestrate.
Mercury can compile/execute/report.
Verifier agents can propose evidence.
certify_run.py + policy_engine.py decide final status.
```

Local smoke-tested state is slightly ahead of the committed v0.5 docs:

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
```

These smokes are local evidence, not automated CI evidence. The full `goal-runner.chain.md` runtime remains unverified. The v0.5.7 smoke produced the expected certifier artifacts, but Pi exited with a stale extension-context error from the installed `@tmustier/pi-agent-teams` extension after output. The v0.5.8 smoke reproduced that failure with the global extension set and then showed a clean exit under a temporary subagents-only Pi config. The v0.5.9 slice adds deterministic session-audit fixtures so duplicate certifier invocations, manual status writes, unsafe deletion, and inferred status after missing reads fail audit. The v0.5.10 slice adds deterministic disposable smoke setup so Pi prompts no longer need to mix copy/setup/certify/report. The v0.5.11 slice adds weak/failing status preservation checks so Pi does not repair or upgrade `NOT_DONE`, `PROVISIONAL_DONE`, or `DONE_FAIL`. The v0.6 slice adds deterministic local host-task certification against disposable runs. The v0.7 slice adds deterministic branch candidates with explicit verifier requirements. The v0.8 slice selects branches by verifier-provenance certifiability while leaving final certification to the certifier. The v0.9 slice adds read-only replay, dry-run rollback, and audit reports that can block certification. The v1.0 slice freezes a thin local command surface and practical examples. The v1.1 slice adds deterministic raw-goal compilation fixtures. The v1.2 slice proves the selected branch handoff into `merged_plan.json` before worker execution and certification.

## What v0.3 proves

v0.3 proves a narrower control principle:

```text
Mercury may propose, plan, execute, and report evidence, but Mercury cannot certify final success.
```

The current proof is limited to the deterministic stub planner and local Python harness. It does not prove real Mercury V2 or Pi agent quality.

The new v0.3 PlanGraph proof is:

```text
planned tasks produce named artifacts, downstream tasks require exact artifact IDs, and certification validates those artifact links.
```

The first verifier-provenance runtime gate is now implemented. It activates only when a run contains `verifier_contract.json`; legacy runs without that contract still use `DONE_PASS` / `DONE_FAIL`.

The v0.3.3 diagnostic slice verifies this behavior using deterministic fixtures only. It is not a broad benchmark.

The harness now requires:

- a valid Goal Contract,
- a Worker step log,
- non-empty evidence,
- `pass_condition_satisfied: true`,
- touched files that really exist inside the run folder,
- required final outputs at the exact contract path,
- executable `artifact_tests` when executable behavior is required,
- a parseable trace log,
- valid PlanGraph artifacts when `plan_graph.json` exists,
- produced artifacts at exact run-relative paths,
- required artifact IDs with valid producer tasks,
- consistent `plan_graph.json`, `artifact_registry.json`, and `task_graph.json`,
- verifier provenance artifacts when `verifier_contract.json` exists,
- verifier smell reports recorded when verifier artifacts exist,
- verifier strength reports recorded when verifier artifacts exist,
- a deterministic `policy_decision.json` when `verifier_contract.json` exists,
- `P0` and `P1` verifier evidence treated as `PROVISIONAL_DONE`,
- `P2` or `P3` certifying verifier evidence with certifying strength required for `CERTIFIED_DONE`,
- and certifier-issued final status.

## What was hardened

The Guarded Worker now writes `create_file` outputs inside `.agentic-runs/<run_id>/` and rejects absolute or escaping paths.

The planner now writes plan JSON only. It no longer creates final artifacts before the worker runs.

The certifier now rejects:

- missing touched files,
- false `pass_condition_satisfied`,
- empty evidence,
- non-empty `remaining_work`,
- protected-file touches,
- merged-plan and step-log path mismatches,
- and final outputs that exist only at a fallback path.
- Worker step logs that touch `verifier_artifacts/`.

In provenance mode, the certifier now returns:

- `NOT_DONE` when required target artifacts or verifier artifacts are missing, or checks fail,
- `PROVISIONAL_DONE` when only `P0` or `P1` verifier evidence exists,
- `CERTIFIED_DONE` when valid `P2` or `P3` certifying evidence satisfies the verifier contract.

In v0.3.4, smell reports are recorded under `verifier_smell_reports/`. These reports are evidence for later policy work; they do not change certification status yet.

In v0.3.5, strength reports are recorded under `verifier_strength_reports/`. These reports are evidence for later policy work; they do not change certification status yet.

In v0.3.6, policy decisions are recorded under `policy_decision.json`. In provenance mode, the certifier uses that policy decision as the final status.

The benchmark now records:

- actual status,
- expected status,
- status match,
- and false-PASS status.

See `docs/V0_2_1_FREEZE.md` for the fake-DONE freeze boundary.
See `docs/V0_3_PLANGRAPH.md` for the PlanGraph prototype boundary.
See `docs/V0_3_2_PROVENANCE_GATE_FREEZE.md` for the provenance runtime gate boundary.
See `docs/V0_3_3_PROVENANCE_GATE_DIAGNOSTICS.md` for the copy-ready provenance diagnostic fixture boundary.
See `docs/V0_3_4_SMELL_SCANNER.md` for the metadata-level smell scanner boundary.
See `docs/V0_3_5_STRENGTH_SCORER.md` for the verifier strength scoring boundary.
See `docs/V0_3_6_POLICY_ENGINE.md` for the policy engine boundary.
See `docs/V0_4_DIAGNOSTIC_EVALUATION.md` for the small diagnostic evaluation boundary.
See `docs/V0_5_PI_INTEGRATION.md` for the Pi integration contract boundary.
See `docs/V0_5_RUNTIME_SMOKES.md` for the local Pi runtime smoke boundary.
See `docs/V0_5_7_CONTROLLED_MINI_CHAIN_SMOKE.md` for the controlled mini-chain smoke boundary.
See `docs/V0_5_8_PI_CLEAN_EXIT_SMOKE.md` for the Pi clean-exit isolation boundary.
See `docs/V0_5_9_PI_COMMAND_DISCIPLINE_GATE.md` for the Pi command-discipline audit boundary.
See `docs/V0_5_10_DISPOSABLE_SMOKE_HARNESS.md` for the disposable Pi smoke setup boundary.
See `docs/V0_5_11_NEGATIVE_STATUS_SAFETY_SMOKE.md` for the negative-status Pi safety boundary.
See `docs/V0_6_LOCAL_CODING_AGENT_HOST_INTEGRATION.md` for the local host integration boundary.
See `docs/V0_7_BRANCH_GENERATION.md` for the branch-generation boundary.
See `docs/V0_8_EVIDENCE_BRANCH_SELECTION.md` for the evidence-seeking branch selection boundary.
See `docs/V0_9_REPLAY_ROLLBACK_AUDIT.md` for the replay / rollback / audit boundary.
See `docs/V1_0_PRACTICAL_PACKAGE_FREEZE.md` for the practical package freeze boundary.
See `docs/V1_0_EXAMPLES.md` for the frozen example set.
See `docs/V1_1_RAW_GOAL_CHAIN_PROOF.md` for the deterministic raw-goal chain proof.
See `docs/V1_2_PLANNING_PROOF_HARDENING.md` for the deterministic planning handoff proof.
See `FRAMEWORK.md` for the conceptual architecture and actual current file map.
See `docs/PI_PROMPT_CONTRACTS.md` for safe Pi prompt patterns.
See `docs/PI_BASH_ALLOWLIST.md` for the current documented bash safety boundary.
See `PROBLEM_AND_GAP.md` and `VERIFIER_PROVENANCE_DESIGN.md` for the current research direction.

## Known limitations

The Pi integration surface is still intentionally small.

It does not yet include:

- full `goal-runner.chain.md` runtime beyond local read-only, disposable certifier-invocation, and controlled mini-chain smokes,
- clean Pi process-level runtime with all globally installed extensions enabled,
- strict live one-bash-call Pi runtime proof for goal-orchestrator,
- general natural-language goal compilation beyond deterministic fixtures,
- live adaptive multi-plan generation beyond deterministic branch fixtures,
- fully parsed YAML policy configuration,
- broad diagnostic evaluation beyond the small v0.4 deterministic diagnostic set,
- workspace-level rollback outside run-folder-owned artifacts,
- replay of live Pi or Mercury execution, beyond deterministic run-folder reports,
- cost budgets,
- or long-term memory quality checks.

The current `run_goal.py` is still a prepared-run orchestrator. It expects an existing run folder and `goal_contract.json`. The v1.2 planning proof runner is deterministic proof glue, not a live autonomous planner.

## Next milestone

The next milestone should harden release readiness without overclaiming full Pi autonomy:

1. add a proof matrix that maps every claim to a command or test,
2. keep the stable command surface thin,
3. keep final status from `certify_run.py` / `policy_engine.py`,
4. keep audit/replay/rollback unable to certify DONE by themselves,
5. and keep false PASS / false `CERTIFIED_DONE` as hard-fail metrics.
