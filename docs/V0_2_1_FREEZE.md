# v0.2.1 Freeze Boundary

This freeze is only for fake-DONE resistance and artifact-test certification.

v0.3 builds on this freeze with the Artifact-Linked PlanGraph prototype. The v0.2.1 claim remains useful as the fake-DONE baseline, but the current mainline status is tracked in `docs/V0_3_PLANGRAPH.md`.

## Included in v0.2.1

- Run-folder containment for worker-created artifacts.
- Planner/worker separation: `plan_router.py` writes plans only.
- Exact final-output path checks.
- Executable `artifact_tests` in Goal Contracts.
- Benchmark scoring by expected verdict, including `false_pass`.
- Benchmark outputs under `benchmark_outputs/` only.

## Deferred beyond v0.2.1

The following ideas are not part of the v0.2.1 claim until they have schemas, tests, and benchmark coverage:

- PlanGraph builders.
- Artifact registry dependency validation.
- Evidence selector.
- Branch selector.
- Pi command integration.

## Generated Artifacts

Fresh benchmark runs may create `.agentic-runs/benchmark_*` folders. These are run evidence, not source files. The benchmark source of truth is:

```text
benchmark_outputs/benchmark_report.md
benchmark_outputs/benchmark_metrics.json
```

Memory logs must not be updated by benchmark runs.
