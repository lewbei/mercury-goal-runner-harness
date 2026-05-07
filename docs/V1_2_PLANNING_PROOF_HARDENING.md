# v1.2 Planning Proof Hardening

This document records the v1.2 planning proof boundary.

## Status

```text
PLANNING PROOF HARDENING IMPLEMENTED
```

## Goal

v1.2 proves one deterministic planning handoff:

```text
raw goal
-> branch candidates
-> selected branch
-> merged_plan.json
-> Guarded Worker
-> verifier policy
-> certifier status
```

This is intentionally narrow. It does not claim live Mercury planning quality or
full autonomous Pi chain runtime.

## New proof tool

The proof runner is:

```text
.agentic-pi/runtime/planning_proof_runner.py
```

The Pi CLI exposes it as:

```text
goal-plan-proof
```

The raw-goal compiler also supports a deterministic proof mode:

```text
planning_p2
```

That mode creates a HARD-complexity raw-goal fixture with P2 verifier evidence,
so branch generation produces multiple candidates before execution.

## What Is Proven

v1.2 proves:

```text
branch_generator.py creates candidate branches
evidence_branch_selector.py selects one branch by verifier-provenance certifiability
selector_audit.json records that status artifacts were absent at selection time
planning_proof_runner.py materializes the selected branch into merged_plan.json
Guarded Worker executes merged_plan.json
PlanGraph validates exact produced/required artifact IDs
certify_run.py / policy_engine.py decide final status
```

The selected branch does not certify DONE. It only becomes the execution plan.

## What Is Not Proven

v1.2 does not prove:

```text
Mercury can generate high-quality plans
Pi can safely run the full goal-runner.chain.md autonomously
the selected branch is semantically optimal
automatic verifier generation is reliable
arbitrary natural-language goals compile correctly
```

## Authority Boundary

The planning rule is:

```text
Planner proposes.
Branch selector selects.
Worker executes.
Verifier evidence is checked.
Policy engine judges the evidence.
Certifier writes final status.
```

Planning artifacts may contain:

```text
branch_manifest.json
branch_decision.json
selected_branch.json
merged_plan.json
plan_graph.json
artifact_registry.json
task_graph.json
planning_proof.json
```

Planning artifacts may not write or upgrade:

```text
final_status.md
certification.json
policy_decision.json
verifier_artifacts/
```

## Proof Commands

```cmd
python .agentic-pi\runtime\pi_cli.py goal-compile pi_smoke_planning_proof_p2 --goal "Create README.md explaining the harness" --mode planning_p2
python .agentic-pi\runtime\pi_cli.py goal-plan-proof pi_smoke_planning_proof_p2
python .agentic-pi\runtime\pi_cli.py goal-status pi_smoke_planning_proof_p2 --fail-on-missing
```

Expected final status:

```text
CERTIFIED_DONE
```

The expected status is certifier-owned. It is not branch-owned.
