# Current Runtime Path

Status: cleanup guide / source-of-truth pointer

## Authority invariant

```text
Pi can orchestrate.
Mercury can compile / execute / report.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

This file does not certify DONE.

## Strict authority path

The authority path is:

```text
verifier_contract.json
verifier_artifacts/
verifier_smell_reports/
verifier_strength_reports/
policy_decision.json
certification.json
final_status.json
final_status.md
```

Final status is owned by:

```text
.agentic-pi/validators/certify_run.py
.agentic-pi/runtime/policy_engine.py
```

`final_status.json` is the machine-readable authority artifact. `final_status.md` is a derived human-readable view.

## Repo-local helper path

The repo-local command helper is:

```cmd
python .agentic-pi/runtime/pi_cli.py --help
```

This helper is not the external Pi agent. It dispatches deterministic harness commands and must not certify DONE by itself.

## Prepared-run path

A prepared run uses:

```cmd
python .agentic-pi/runtime/init_run.py --run-id <run_id>
python .agentic-pi/runtime/run_goal.py "<goal text>" --run-id <run_id>
python .agentic-pi/validators/certify_run.py .agentic-runs/<run_id>
```

`run_goal.py` is orchestration glue. It now treats missing strict proof inputs as failure, not as permission to create generated compatibility artifacts. Treat it as prepared-run automation, not proof that arbitrary natural-language Pi autonomy is safe.

Before the strict verification phase, the run must already contain planner/verifier-owned inputs such as:

```text
goal_contract.json
expected_artifacts.json
plans/*_plan.json
selected_plan.json
merged_plan.json
plan_graph.json
verifier_contract.json
verifier_artifacts/*.json
```

## Compatibility / proof-slice paths

The following files contain smoke, compatibility, or proof-slice behavior and should not be treated as the strict authority path without reading their boundaries:

```text
.agentic-pi/runtime/run_pi_chain_smoke.py
.agentic-pi/runtime/run_agentic_autonomy_probe.py
.agentic-pi/runtime/run_real_pi_behavior_evaluation.py
.agentic-pi/runtime/run_real_pi_behavior_matrix.py
```

The default runtime files below are intended to fail closed rather than create generated substitute proof artifacts:

```text
.agentic-pi/runtime/full_verify.py       requires existing proof artifacts; no synthesized plans/contracts
.agentic-pi/runtime/orchestrate_pipeline.py fails on any phase failure
.agentic-pi/runtime/plan_router.py       checks for existing plans/*_plan.json only
.agentic-pi/runtime/plan_selector.py     selects among valid existing planner plans only
.agentic-pi/runtime/plan_merger.py       writes merged_plan.json from selected_plan.json only
.agentic-pi/runtime/guarded_worker.py    supports create_file steps only; unknown actions fail
.agentic-pi/runtime/run_subagent_memory.py writes run-local/quarantine candidates only; no direct durable writes
.agentic-pi/runtime/memory_write_gate.py promotes schema-valid advisory cards after certifier-owned final_status.json
```

Cleanup rule for future work:

```text
Strict runtime paths must not silently manufacture missing proof artifacts.
Compatibility or proof-slice tools must clearly say when they are not the strict authority path.
```

## Deprecated / compatibility docs

Root files are compatibility pointers:

```text
PROJECT_STATUS.md -> docs/PROJECT_STATUS.md
FRAMEWORK.md -> docs/FRAMEWORK.md
workspace_index.md -> docs/workspace_index.md
```

The canonical long-form docs remain under `docs/`.
