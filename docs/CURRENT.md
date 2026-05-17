# Current Harness State

Status: canonical human-readable current-state pointer. This file does not certify DONE.

## Authority invariant

```text
Pi can orchestrate.
Mercury can compile / execute / report.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

Do not manually edit:

```text
final_status.json
final_status.md
certification.json
policy_decision.json
```

## Current bounded proof path

The current strongest planning path is the bounded planning-quality handoff:

```text
Stage 3 runtime preflight
  -> Planning Coordination v1 completeness gate
  -> Planning Coordination v1.1 quality gate
  -> Guarded Execution v2 handoff
  -> policy_engine.py / certify_run.py authority path
```

This path is evidence-gated and execution-blocking for the guarded v2 slice. It does not prove that every historical runner, smoke harness, or legacy compatibility path is globally forced through v1.1.

## Latest certified planning milestones

| Milestone | Commit | Certified run | Status |
| --- | --- | --- | --- |
| Planning Efficiency v3 bounded repair loop | `21eb510` | `.agentic-runs/planning_efficiency_v3_handoff_20260514_091756` | `CERTIFIED_DONE` |
| Planning Coordination v1 completeness gate | `8d9532f` | `.agentic-runs/pcv1_20260517_040521` | `CERTIFIED_DONE` |
| Planning Coordination v1.1 quality gate | `b7315fe` | `.agentic-runs/pcv11_20260517_044439` | `CERTIFIED_DONE` |

Latest v1.1 status summary:

```text
checks_passed: 96
checks_failed: 0
final_status_authority: certifier_only
can_certify_done: false
```

## Current validation commands

Use checks as evidence, not as self-certification.

```cmd
python tests\test_planning_coordination_v1_1_quality.py -v
python tests\test_planning_coordination_v1.py -v
python tests\test_planning_efficiency_v3_repair_loop.py -v
python tests\test_guarded_execution_v2.py -v
python tests\test_planning_efficiency_v2.py -v
python tests\test_v2_proof_package.py -v
python .agentic-pi\runtime\run_proof_matrix.py --mode quick
python tests\test_repo_structure_cleanup.py -v
python .agentic-pi\validators\validate_final_status.py .agentic-runs\pcv11_20260517_044439\final_status.json
git diff --check
git status -sb
```

## Package / install boundary

This repository is currently a harness/research repo, not a polished reusable Python package.

For Pi harness installation, the repo name is:

```cmd
pi install git:github.com/lewbei/mercury-goal-runner-harness
```

Local development may use:

```cmd
pi install .
```

If a separate package named `mercury-goal-runner` exists, treat it as a separate install target. Do not assume it is the same repository as this harness.

No `pyproject.toml`, `setup.py`, or `requirements.txt` claim is made by this file. Adding formal package metadata should be a separate package milestone with tests.

## Historical docs boundary

Versioned docs under `docs/V*.md` are historical proof records, design notes, or compatibility notes unless this file or `docs/CURRENT_RUNTIME_PATH.md` says they are the current runtime contract.

Current pointers:

```text
docs/CURRENT.md              canonical current-state pointer
docs/CURRENT_RUNTIME_PATH.md strict runtime path and compatibility map
docs/PLAN_ROUTER.md         strict plan-router boundary
docs/PROJECT_STATUS.md      historical status ledger and roadmap context
docs/workspace_index.md     file map and cleanup debt
```

## Implemented hardening notes

```text
artifact test command execution is allowlisted for run-relative Python scripts only
unsafe shell operators, Python -c/-m style eval, path escapes, protected status artifact references, and unknown executables fail closed
```

## Still valid gaps

```text
docs/package cleanup beyond this pointer still needs follow-up
certifier is still a large monolith
Stage 2 semantic/live evaluation still needs expansion
task routing can still improve
skeptic planner is not yet mandatory across all paths
no MCTS / symbolic bridge / partial-observability planner yet
```

Safe claim:

```text
The harness passed the listed deterministic validators and proof commands for the bounded planning/guarded-execution slices.
```

Unsafe claim:

```text
Pi/Mercury is proven safe for arbitrary autonomous goals.
```
