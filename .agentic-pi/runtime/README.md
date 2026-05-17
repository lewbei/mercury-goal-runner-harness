# Runtime Folder

Status: source-of-truth ownership map for `.agentic-pi/runtime`.

This folder is currently flat because most tools are runnable script entrypoints.
Do not move files into subpackages without first adding import and CLI smoke
tests for every affected entrypoint.

Final status comes only from `certify_run.py` and `policy_engine.py`. Runtime
helpers can prepare, execute, trace, replay, or audit, but they cannot certify DONE by themselves.

## Current Strict Runtime Boundary

The default runtime path is fail-closed:

```text
full_verify.py       requires existing planning_search_tree.json, planning_coverage.json, proof artifacts, and verifier evidence; it validates adaptive_research_inputs.json when present and does not create missing plans or verifier contracts
plan_router.py       requires existing plans/*_plan.json; it does not synthesize SIMPLE/MEDIUM/HARD plans
plan_selector.py     validates and selects among existing planner-owned plans
plan_merger.py       writes merged_plan.json from selected_plan.json only
guarded_worker.py    executes create_file steps only; unsupported actions fail
orchestrate_pipeline.py returns failure when any phase fails
run_subagent_memory.py writes run-local/quarantine memory only; no direct durable writes
memory_write_gate.py is the only durable-memory promotion path
```

Historical smoke/proof tools remain in this folder, but they are compatibility or evidence slices, not the current authority path.

## Module Groups

Goal, prompt provenance, and run setup:

```text
init_run.py
compile_raw_goal.py
write_goal_contract.py
prompt_provenance.py
setup_pi_smoke.py
orchestrate_pipeline.py
```

`prompt_provenance.py` records raw prompt -> `execution_prompt` metadata under
`.agentic-runs/<run_id>/prompt_provenance/`. This artifact is provenance-only;
it cannot certify DONE or replace verifier evidence.

Planning and strategy:

```text
adaptive_research_inputs.py
plan_router.py
plan_selector.py
planning_proof_runner.py
planning_coverage.py
planning_search_tree.py
roadmap_planner.py
strategy_*.py
milestone_*.py
local_step_planner.py
step_compiler.py
plan_merger.py
```

`adaptive_research_inputs.py` writes run-local
`adaptive_research_inputs.json`, the Option A boundary for adaptive or
non-deterministic autoresearch: saved findings may shape planning questions,
risk notes, and verifier follow-up, but deterministic validators consume only
recorded provenance and research cannot certify DONE. `planning_search_tree.py`
writes run-local `planning_search_tree.json`, a bounded depth-limited tree trace
over task type, strategy, execution, verifier, risk, adaptive research inputs,
and deferred branches. It now records search iterations, score components,
GitHub-method influences (ToT/GoT/LATS), and explicitly deferred expansion
methods such as LLM voting, graph aggregation, adaptive live research, and MCTS
rollouts. `planning_coverage.py` writes run-local `planning_coverage.json`,
recording selected/rejected/deferred planning branches, assumptions, risks,
verifier handoff, ask-user triggers, and false-DONE traps. These artifacts
include boundaries saying they do not prove all possible plans and do not prove
artifact correctness. They are planning evidence only; none claims exhaustive
planning, correctness, or final-status authority.

Execution and artifacts:

```text
guarded_worker.py
run_goal.py
trace_logger.py
artifact_linker.py
task_graph_builder.py
plan_graph_builder.py
```

Verifier provenance, policy, and certification support:

```text
verifier_provenance.py
policy_engine.py
full_verify.py
verify_agent_outputs.py
```

Pi and Mercury proof tools:

```text
pi_cli.py
pi_session_audit.py
pi_direct_behavior_audit.py
pi_real_session_monitor.py
pi_session_trace_monitor.py
run_pi_chain_smoke.py
run_real_pi_trace_smoke.py
run_agentic_autonomy_probe.py
run_live_negative_prompt_capture.py
run_real_pi_behavior_evaluation.py
run_real_pi_behavior_matrix.py
```

Memory, domain, and workflow search:

```text
experience_*.py
learning_record_writer.py
strategy_memory.py
run_memory_clerk.py
quarantine_memory_writer.py
memory_write_gate.py
mempalace_adapter.py
context_pack_builder.py
domain_pack_selector.py
workflow_search.py
```

Replay, rollback, audit, and drift:

```text
audit_run.py
replay_run.py
rollback_run.py
checkpoint_writer.py
plan_monitor.py
drift_detector.py
replan_controller.py
drift_proof_runner.py
```

## Next Refactor Rule

The next physical cleanup should be:

```text
add import/entrypoint tests first
move one module group
run full proof gate
commit
```

Do not move everything at once.
