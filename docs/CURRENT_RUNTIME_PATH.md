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

`final_status.json` is the machine-readable authority artifact. `final_status.md` is a derived human-readable view. In the normal provenance path, `final_status.json` cites `policy_decision.json`; when a later certifier gate blocks the run, it cites `certification.json` and records a blocking status.

Artifact test commands declared in `goal_contract.json` are not a general shell surface. The certifier allowlists only run-relative Python script commands and rejects shell operators, Python eval/module shortcuts, absolute/path-escaping scripts, protected status artifact references, and unknown executables before execution.

## Repo-local helper path

The repo-local command helper is:

```cmd
python .agentic-pi/runtime/pi_cli.py --help
```

This helper is not the external Pi agent. It dispatches deterministic harness commands and must not certify DONE by itself.

`pi_cli.py goal-compile --mode legacy` is deprecated compatibility-only. Do not use it as the recommended walkthrough or authority path; use strict verifier-provenance inputs instead.

Strict raw-goal fixture smoke uses verifier provenance by default (`--mode p2` is the default, and `--mode planning_p2` is the stricter planning proof fixture):

```cmd
python .agentic-pi/runtime/pi_cli.py goal-compile strict_mock_goal --goal "Create README.md explaining the harness" --mode p2
python .agentic-pi/runtime/pi_cli.py goal-run strict_mock_goal --skip-memory-update
python .agentic-pi/runtime/pi_cli.py goal-status strict_mock_goal --fail-on-missing
```

Expected authority artifacts for that path include `verifier_contract.json`, `verifier_artifacts/V.RAW_GOAL_P2.json`, `policy_decision.json`, `certification.json`, and `final_status.json` with `CERTIFIED_DONE` only after policy/certifier checks pass.

## Prepared-run path

A prepared run uses:

```cmd
python .agentic-pi/runtime/init_run.py --run-id <run_id>
# create planner/verifier-owned prerequisites listed below
python .agentic-pi/runtime/full_verify.py .agentic-runs/<run_id>
```

`full_verify.py` is the recommended strict local command path. `run_goal.py` is orchestration glue around prepared runs; it treats missing strict proof inputs as failure, not as permission to create generated compatibility artifacts. Treat either command as prepared-run automation, not proof that arbitrary natural-language Pi autonomy is safe.

Before the strict verification phase, the run must already contain planner/verifier-owned inputs such as:

```text
goal_contract.json
planning_search_tree.json
planning_coverage.json
expected_artifacts.json
plans/*_plan.json
selected_plan.json
merged_plan.json
plan_graph.json
verifier_contract.json
verifier_artifacts/*.json
```

Optional adaptive/autoresearch planning input, when present, must be run-local and validator-clean:

```text
adaptive_research_inputs.json
```

## Current bounded planning-quality proof path

The strongest current planning path is bounded and evidence-gated:

```text
stage3_runtime_preflight.py
  -> planning_coordination_v1.py
  -> planning_coordination_v1_1_quality.py
  -> guarded_execution_v2.py
  -> policy_engine.py / certify_run.py
```

Planning Coordination v1.1 adds evidence-weighted quality scoring, mandatory selected-candidate skeptic/attack review, blocker/unknown budget checks, selected-handoff revalidation, and handoff binding to Guarded Execution v2. It is allowed to approve or block a handoff; unresolved high-severity or authority risks must block the handoff. It must not execute the guarded plan and must not certify DONE.

Boundary: this is the current bounded proof path for the guarded v2 slice. It does not mean every historical runner, smoke harness, or compatibility path is globally forced through v1.1.

The current-state summary lives at:

```text
docs/CURRENT.md
```

## Compatibility / proof-slice paths

The following files contain smoke, compatibility, deprecated legacy, or proof-slice behavior and should not be treated as the strict authority path without reading their boundaries:

```text
.agentic-pi/runtime/run_pi_chain_smoke.py
.agentic-pi/runtime/run_agentic_autonomy_probe.py
.agentic-pi/runtime/run_real_pi_behavior_evaluation.py
.agentic-pi/runtime/run_real_pi_behavior_matrix.py
.agentic-pi/runtime/compile_raw_goal.py --mode legacy
```

The default runtime files below are intended to fail closed rather than create generated substitute proof artifacts:

```text
.agentic-pi/runtime/full_verify.py       recommended strict path; requires existing planning search/coverage, proof artifacts, and verifier evidence; validates adaptive research inputs when present; no synthesized plans/contracts
.agentic-pi/runtime/orchestrate_pipeline.py lower-level deterministic phase runner; fails on any phase failure
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
