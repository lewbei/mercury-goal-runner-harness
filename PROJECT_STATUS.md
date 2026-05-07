# Project Status

## Current version

Mercury Goal Runner Harness v2.7 is the Real Pi Agentic Autonomy Probe on top of the v2.6 Real Pi Session Trace Capture.

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
python .agentic-pi\diagnostics\trajectory_evaluation\run_trajectory_evaluation.py
python .agentic-pi\benchmark\run_benchmark.py
python .agentic-pi\runtime\pi_cli.py --help
python .agentic-pi\runtime\run_proof_matrix.py --mode quick
python .agentic-pi\runtime\run_pi_chain_smoke.py --target-run-id pi_smoke_chain_p2_strong
python tests\test_pi_direct_behavior_audit.py -v
python tests\test_pi_real_interactive_smoke_docs.py -v
python tests\test_pi_real_session_monitor.py -v
python tests\test_pi_session_trace_capture.py -v
python tests\test_agentic_autonomy_probe.py -v
```

Naming boundary:

```text
pi = the real external Pi agent launched from cmd.
.agentic-pi/runtime/pi_cli.py = repo-local deterministic harness helper.
```

`pi_cli.py` is not the Pi agent. It only dispatches this repo's deterministic
harness commands.

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
v1.3 = Strategy planner IMPLEMENTED
v1.4 = Milestone planning IMPLEMENTED
v1.5 = Drift-aware replanning IMPLEMENTED
v1.6 = Trajectory-level evaluation IMPLEMENTED
v1.7 = Experience memory IMPLEMENTED
v1.8 = Domain packs IMPLEMENTED
v1.9 = Strategy search IMPLEMENTED
v2.0 = Integrated proof package IMPLEMENTED
v2.1 = Controlled Pi chain runtime proof IMPLEMENTED
v2.2 = Direct Pi/Mercury behavior audit IMPLEMENTED
v2.3 = Real Pi interactive smoke evidence RECORDED
v2.4 = Real Pi run monitor IMPLEMENTED
v2.5 = Real Pi negative-status smoke monitor IMPLEMENTED
v2.6 = Real Pi session trace capture IMPLEMENTED
v2.7 = Real Pi agentic autonomy probe IMPLEMENTED
```

These smokes are local evidence, not automated CI evidence. The full `goal-runner.chain.md` runtime remains unverified for arbitrary goals. The v0.5.7 smoke produced the expected certifier artifacts, but Pi exited with a stale extension-context error from the installed `@tmustier/pi-agent-teams` extension after output. The v0.5.8 smoke reproduced that failure with the global extension set and then showed a clean exit under a temporary subagents-only Pi config. The v0.5.9 slice adds deterministic session-audit fixtures so duplicate certifier invocations, manual status writes, unsafe deletion, and inferred status after missing reads fail audit. The v0.5.10 slice adds deterministic disposable smoke setup so Pi prompts no longer need to mix copy/setup/certify/report. The v0.5.11 slice adds weak/failing status preservation checks so Pi does not repair or upgrade `NOT_DONE`, `PROVISIONAL_DONE`, or `DONE_FAIL`. The v0.6 slice adds deterministic local host-task certification against disposable runs. The v0.7 slice adds deterministic branch candidates with explicit verifier requirements. The v0.8 slice selects branches by verifier-provenance certifiability while leaving final certification to the certifier. The v0.9 slice adds read-only replay, dry-run rollback, and audit reports that can block certification. The v1.0 slice freezes a thin local command surface and practical examples. The v1.1 slice adds deterministic raw-goal compilation fixtures. The v1.2 slice proves the selected branch handoff into `merged_plan.json` before worker execution and certification. The v1.3 slice adds deterministic task-type routing, capability inventory, strategy candidates, applicability gating, scoring, selection, and step compilation. The v1.4 slice adds deterministic milestone planning and local step planning between selected strategy and `merged_plan.json`. The v1.5 slice adds checkpoints, plan monitoring, drift reports, bounded delta plans, and certifier blocking for unresolved drift. The v1.6 slice adds trajectory-level tool-use evaluation for tool choice, arguments, order, duplicate certifier calls, manual writes, missing reads, and unsafe deletion. The v1.7 slice adds advisory experience memory that can extract lessons, write append-only records, retrieve relevant principles, and adjust strategy scores without certifying DONE. The v1.8 slice adds deterministic domain packs that shape strategy candidates and verifier hints without certifying DONE. The v1.9 slice adds deterministic workflow search that rejects certifier-bypass and high false-certified-risk candidates without executing or certifying. The v2.0 slice adds an integrated proof matrix and examples without claiming full Pi autonomy. The v2.1 slice adds a controlled Pi chain smoke for verifier-generator -> verifier-reviewer -> goal-orchestrator without claiming arbitrary Pi chain autonomy. The v2.2 slice adds direct Pi/Mercury behavior audit fixtures that require verifier evidence before certifier invocation, status reads after certifier invocation, and no self-certifying assistant language. The v2.3 slice records a real `pi` interactive smoke result as local evidence, not automated CI evidence. The v2.4 slice monitors captured real Pi transcript fixtures for exactly-one-command discipline, required result reads, protected-write attempts, and self-certifying language. The v2.5 slice extends that monitor to weak/failing status transcripts and rejects assistant-side upgrades such as `PROVISIONAL_DONE` to `CERTIFIED_DONE`. The v2.6 slice normalizes captured Pi output into `pi_session_trace.jsonl` and monitors the trace directly. The v2.7 slice runs and monitors a real Pi/Mercury agentic autonomy probe that reads the chain, reads advisory memory, observes an initial certifier failure, performs one run-local repair, reruns the certifier, and reports certifier-owned status artifacts. It does not prove arbitrary unbounded bash or arbitrary goal-runner.chain.md autonomy is safe.

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
See `docs/V1_3_STRATEGY_PLANNER.md` for the deterministic strategy-planner proof.
See `docs/V1_4_MILESTONE_PLANNING.md` for the deterministic milestone-planning proof.
See `docs/V1_5_DRIFT_AWARE_REPLANNING.md` for the deterministic drift-aware replanning proof.
See `docs/V1_6_TRAJECTORY_LEVEL_EVALUATION.md` for the trajectory-level evaluation proof.
See `docs/V1_7_EXPERIENCE_MEMORY.md` for the advisory experience-memory proof.
See `docs/V1_8_DOMAIN_PACKS.md` for the domain-pack proof.
See `docs/V1_9_STRATEGY_SEARCH.md` for the workflow-search proof.
See `docs/V2_0_INTEGRATED_HARNESS_PROOF_PACKAGE.md` for the integrated proof package.
See `docs/V2_0_EXAMPLES.md` for the v2.0 example set.
See `docs/V2_1_CONTROLLED_PI_CHAIN_RUNTIME_PROOF.md` for the controlled Pi chain runtime proof.
See `docs/V2_2_DIRECT_PI_MERCURY_BEHAVIOR_AUDIT.md` for the direct Pi/Mercury behavior audit proof.
See `docs/V2_3_REAL_PI_INTERACTIVE_SMOKE.md` for the real Pi interactive smoke evidence boundary.
See `docs/V2_4_REAL_PI_RUN_MONITOR.md` for the captured real Pi run monitor boundary.
See `docs/V2_5_REAL_PI_NEGATIVE_STATUS_SMOKE.md` for the real Pi negative-status monitor boundary.
See `docs/V2_6_REAL_PI_SESSION_TRACE_CAPTURE.md` for the real Pi session trace boundary.
See `docs/V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md` for the completed v1.3-v2.0 roadmap.
See `FRAMEWORK.md` for the conceptual architecture and actual current file map.
See `docs/PI_PROMPT_CONTRACTS.md` for safe Pi prompt patterns.
See `docs/PI_BASH_ALLOWLIST.md` for the current documented bash safety boundary.
See `PROBLEM_AND_GAP.md` and `VERIFIER_PROVENANCE_DESIGN.md` for the current research direction.

## Known limitations

The Pi integration surface is still intentionally small.

It does not yet include:

- full `goal-runner.chain.md` runtime beyond local read-only, disposable certifier-invocation, controlled mini-chain smokes, and the bounded v2.1 Pi chain smoke,
- clean Pi process-level runtime with all globally installed extensions enabled,
- strict internal Pi tool-call audit for arbitrary live Pi chain smokes,
- strict live one-bash-call Pi runtime proof for goal-orchestrator,
- general natural-language goal compilation beyond deterministic fixtures,
- live adaptive multi-plan generation beyond deterministic branch fixtures,
- fully parsed YAML policy configuration,
- broad diagnostic evaluation beyond the small v0.4 deterministic diagnostic set,
- workspace-level rollback outside run-folder-owned artifacts,
- replay of live Pi or Mercury execution, beyond deterministic run-folder reports,
- cost budgets,
- or long-term memory quality checks.

The current `run_goal.py` is still a prepared-run orchestrator. It expects an existing run folder and `goal_contract.json`. The v1.5 drift proof runner, v1.6 trajectory evaluator, v1.7 experience memory tools, v1.8 domain-pack tools, v1.9 workflow-search tools, v2.0 proof matrix, v2.1 controlled Pi chain smoke, v2.2 direct behavior audit, v2.3 real Pi interactive smoke evidence, v2.4 real Pi run monitor, v2.5 real Pi negative-status smoke monitor, and v2.6 real Pi session trace capture are proof glue, not a live autonomous planner.

The v1.3-v2.0 roadmap has now been implemented as deterministic proof slices. The v2.1 controlled Pi chain smoke is also implemented. Remaining future work is beyond this plan:

- external host integrations,
- arbitrary full Pi chain autonomy,
- large benchmark validity,
- paper experiment packaging.

## Next milestone

The next milestone should be chosen deliberately. The safe next candidates are:

1. full Pi chain runtime proof,
2. external local coding-agent host integration beyond fixtures,
3. or paper-style experiment packaging.

Do not claim any of those until they have their own proof matrix entries.
