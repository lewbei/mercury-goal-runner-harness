# v0.3 Artifact-Linked PlanGraph Prototype

v0.3 is PlanGraph only.

It does not add evidence-seeking branch selection, Pi commands, memory behavior, or a real Mercury planner. The claim is narrower:

```text
planned tasks produce named artifacts, downstream tasks require exact artifact IDs, and certification validates those artifact links.
```

## Included in v0.3

- `plan_graph.json` with task nodes, artifact nodes, and typed `produces` / `requires` edges.
- `artifact_registry.json` with canonical artifact IDs, run-relative paths, producer task, required-by tasks, type, and post-worker validation status.
- `task_graph.json` with task IDs, required artifact IDs, produced artifact IDs, and dependency edges.
- Stable `task_id`, `requires`, and `produces` fields in `merged_plan.json` steps.
- Graph validation inside `certify_run.py` when `plan_graph.json` exists.
- A two-step dependency benchmark where `T2` requires the exact artifact produced by `T1`.

## Validation Rules

The PlanGraph validator rejects:

- produced artifacts missing at the exact run-relative path,
- required artifact IDs with no producer,
- tasks that require artifacts produced later,
- artifact paths that escape `.agentic-runs/<run_id>/`,
- mismatches between `plan_graph.json`, `artifact_registry.json`, and `task_graph.json`,
- and graph files with unknown schema fields.

## Current Local Evidence

```text
python -m unittest discover tests -v
python .agentic-pi\benchmark\run_benchmark.py
```

Latest benchmark source of truth:

```text
benchmark_outputs/benchmark_report.md
benchmark_outputs/benchmark_metrics.json
```

The current benchmark includes simple, medium, hard, impossible/risky, and long-range dependency cases. The dependency case passes only when `T2` consumes `A.SOURCE`, the exact artifact ID produced by `T1`.

## Deferred

These remain outside the v0.3 claim:

- evidence-seeking branch selection,
- branch rejection based on missing evidence,
- Pi CLI commands,
- real Mercury/Pi agent orchestration,
- replay and rollback,
- and research baseline comparisons.
