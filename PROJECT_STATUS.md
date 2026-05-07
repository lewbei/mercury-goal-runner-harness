# Project Status

## Current version

Mercury Goal Runner Harness v0.3.3 is Provenance Gate Diagnostic Tests on top of the v0.3.2 Provenance Runtime Gate.

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
python .agentic-pi\benchmark\run_benchmark.py
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
- `P0` and `P1` verifier evidence treated as `PROVISIONAL_DONE`,
- `P2` or `P3` certifying verifier evidence required for `CERTIFIED_DONE`,
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

The benchmark now records:

- actual status,
- expected status,
- status match,
- and false-PASS status.

See `docs/V0_2_1_FREEZE.md` for the fake-DONE freeze boundary.
See `docs/V0_3_PLANGRAPH.md` for the PlanGraph prototype boundary.
See `docs/V0_3_2_PROVENANCE_GATE_FREEZE.md` for the provenance runtime gate boundary.
See `docs/V0_3_3_PROVENANCE_GATE_DIAGNOSTICS.md` for the copy-ready provenance diagnostic fixture boundary.
See `PROBLEM_AND_GAP.md` and `VERIFIER_PROVENANCE_DESIGN.md` for the current research direction.

## Known limitations

v0.3 is still intentionally small.

It does not yet include:

- real Mercury/Pi planner invocation,
- automatic rough-goal to contract compilation from the user-facing command,
- adaptive multi-plan generation,
- smell scanning,
- verifier strength scoring,
- full certification policy engine backed by `certification_policy.yaml`,
- broad diagnostic evaluation beyond the four-case provenance gate check,
- rollback validation,
- replay validation,
- cost budgets,
- or long-term memory quality checks.

The current `run_goal.py` is still a prepared-run orchestrator. It expects an existing run folder and `goal_contract.json`.

## Next milestone

The next milestone should add verifier quality checks after the v0.3.3 diagnostic set remains stable:

1. add smell scanning,
2. add verifier strength scoring,
3. connect the static policy draft to a deterministic policy engine,
4. add a small diagnostic suite,
5. and keep false PASS as the main hard-fail metric.
