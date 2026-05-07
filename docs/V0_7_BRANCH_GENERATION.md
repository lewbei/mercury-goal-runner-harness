# v0.7 Branch Contract and Deterministic Branch Generation

This document records the v0.7 branch-generation slice.

It creates candidate PlanGraph branches. It does not execute branches and does
not certify DONE.

## Status

```text
BRANCH CONTRACT AND GENERATION IMPLEMENTED
```

## Rule

```text
Branches are candidate execution plans.
Branches are not verifier evidence.
Branches cannot produce DONE_PASS, PROVISIONAL_DONE, or CERTIFIED_DONE.
```

Final status still comes only from:

```text
certify_run.py
policy_engine.py
```

## Schemas

New tracked schemas:

```text
branch_candidate.schema.json
branch_manifest.schema.json
artifact_registry.schema.json
```

Each branch candidate records:

```text
branch_id
planner_id
planner_role
goal_contract_hash
plan_graph_path
artifact_registry_path
task_graph_path
verifier_requirements
known_risks
selection_state
```

## Runtime

The deterministic generator is:

```text
.agentic-pi/runtime/branch_generator.py
```

It generates:

```text
SIMPLE -> minimal
MEDIUM -> minimal, robust
HARD/RISKY -> minimal, robust, skeptic
```

Each branch gets:

```text
branches/<branch_id>/branch_candidate.json
branches/<branch_id>/plan_graph.json
branches/<branch_id>/artifact_registry.json
branches/<branch_id>/task_graph.json
```

## Validation

The validator rejects:

```text
branch claiming forbidden final authority
missing verifier requirements
duplicate artifact IDs inside a branch
path escapes
planner touches to verifier_artifacts/
missing branch artifacts
```

## Safe claim

Safe claim:

```text
The harness can generate deterministic candidate branches with explicit
verifier requirements and reject branches that try to become certification
authority.
```

Unsafe claim:

```text
The best branch certifies DONE.
```

That remains false. Branch selection and certification are separate.

## Proof commands

```cmd
python tests\test_branch_generation.py -v
python -m unittest discover tests -v
python .agentic-pi\diagnostics\evaluation\run_diagnostic_evaluation.py
python .agentic-pi\benchmark\run_benchmark.py
```
