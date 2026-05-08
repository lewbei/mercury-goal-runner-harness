# Runtime Folder

Status: source-of-truth ownership map for `.agentic-pi/runtime`.

This folder is currently flat because most tools are runnable script entrypoints.
Do not move files into subpackages without first adding import and CLI smoke
tests for every affected entrypoint.

Final status comes only from `certify_run.py` and `policy_engine.py`. Runtime
helpers can prepare, execute, trace, replay, or audit, but they cannot certify DONE by themselves.

## Module Groups

Goal and run setup:

```text
init_run.py
compile_raw_goal.py
write_goal_contract.py
setup_pi_smoke.py
```

Planning and strategy:

```text
plan_router.py
plan_selector.py
planning_proof_runner.py
strategy_*.py
milestone_*.py
local_step_planner.py
step_compiler.py
plan_merger.py
```

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
```

Memory, domain, and workflow search:

```text
experience_*.py
learning_record_writer.py
strategy_memory.py
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
