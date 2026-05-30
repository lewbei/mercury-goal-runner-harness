# Framework

## Core Question

Who is allowed to certify DONE?

## Answer

Agents do work. Policy engine judges the evidence. Certifier writes the final status. Pi only reports what the certifier wrote.

## Authority Model

```
ROLES:
  Constitution: rules (AGENTS.md, .agentic-pi/rules/)
  CEO: orchestrator (Pi)
  Planners: plan builders (plan_builders subagent)
  Skeptic: critic (skeptic subagent)
  Worker: implementer (guarded_worker)
  Supervisor: validator (verify_agent_outputs)
  Certifier: judge (certify_run.py, policy_engine.py)

RULES:
  Planner cannot verify own plan
  Worker cannot certify own work
  Supervisor cannot modify worker code
  Certifier cannot be overridden by Pi
  Pi cannot edit authority files
  Pi cannot bypass certifier
```

## Pipeline

```
INTAKE -> RESEARCHING -> DESIGNING -> STRUCTURING -> PLANNING
    |
IMPLEMENTING -> VALIDATOR_BUILDING -> VALIDATING
    |
EVIDENCE_INDEXING -> POLICY_DECIDING -> REPLAYING -> CERTIFYING
    |
REPORTING -> MEMORY_CONSOLIDATING -> DONE
```

## Key Files

### Runtime

- `.agentic-pi/runtime/run_goal.py` - main pipeline
- `.agentic-pi/runtime/guarded_worker.py` - step execution
- `.agentic-pi/runtime/verification_checkpoint.py` - planning verification
- `.agentic-pi/runtime/step_verifier.py` - step verification
- `.agentic-pi/runtime/replanning_loop.py` - replanning
- `.agentic-pi/runtime/context_manager.py` - context management
- `.agentic-pi/runtime/long_horizon_manager.py` - long-horizon support
- `.agentic-pi/runtime/parallel_executor.py` - parallel execution
- `.agentic-pi/runtime/research_module.py` - research module
- `.agentic-pi/runtime/resume_module.py` - resume mechanism
- `.agentic-pi/runtime/cross_run_learner.py` - cross-run learning
- `.agentic-pi/runtime/compile_raw_goal.py` - goal compilation
- `.agentic-pi/runtime/planning_proof_runner.py` - planning proof
- `.agentic-pi/runtime/task_type_router.py` - task routing
- `.agentic-pi/runtime/domain_pack_selector.py` - domain pack selection
- `.agentic-pi/runtime/workflow_search.py` - workflow search
- `.agentic-pi/runtime/run_proof_matrix.py` - proof matrix
- `.agentic-pi/runtime/run_pi_chain_smoke.py` - chain smoke test
- `.agentic-pi/runtime/pi_direct_behavior_audit.py` - behavior audit
- `.agentic-pi/runtime/pi_real_session_monitor.py` - session monitor
- `.agentic-pi/runtime/pi_session_trace_monitor.py` - trace monitor
- `.agentic-pi/runtime/run_real_pi_trace_smoke.py` - trace smoke test
- `.agentic-pi/runtime/run_live_negative_prompt_capture.py` - negative capture
- `.agentic-pi/runtime/run_real_pi_behavior_evaluation.py` - behavior evaluation
- `.agentic-pi/runtime/run_real_pi_behavior_matrix.py` - behavior matrix
- `.agentic-pi/runtime/command_gateway.py` - command gateway
- `.agentic-pi/runtime/protected_file_guard.py` - file guard
- `.agentic-pi/runtime/run_enforced_pi_smoke.py` - enforced smoke test
- `.agentic-pi/runtime/rpg_test_aggregator.py` - test aggregator
- `.agentic-pi/runtime/final_status_renderer.py` - status renderer
- `.agentic-pi/runtime/evidence_indexer.py` - evidence indexer
- `.agentic-pi/runtime/evidence_freezer.py` - evidence freezer
- `.agentic-pi/runtime/run_memory_clerk.py` - memory clerk
- `.agentic-pi/runtime/quarantine_memory_writer.py` - quarantine memory
- `.agentic-pi/runtime/mempalace_adapter.py` - mempalace adapter
- `.agentic-pi/runtime/context_pack_builder.py` - context pack builder
- `.agentic-pi/runtime/ace_reflector.py` - ACE reflector
- `.agentic-pi/runtime/ace_curator.py` - ACE curator
- `.agentic-pi/runtime/memory_write_gate.py` - memory write gate
- `.agentic-pi/runtime/capability_inventory.py` - capability inventory
- `.agentic-pi/runtime/orchestrate_pipeline.py` - pipeline orchestration
- `.agentic-pi/runtime/pi_cli.py` - Pi CLI
- `.agentic-pi/runtime/harness_health.py` - health check
- `.agentic-pi/runtime/auto_dispatcher.py` - auto dispatcher
- `.agentic-pi/runtime/context_injector.py` - context injector
- `.agentic-pi/runtime/smart_memory.py` - smart memory
- `.agentic-pi/runtime/plan_graph_v1_builder.py` - plan graph builder
- `.agentic-pi/runtime/audit_run.py` - audit run
- `.agentic-pi/runtime/replay_run.py` - replay run
- `.agentic-pi/runtime/rollback_run.py` - rollback run
- `.agentic-pi/runtime/strategy_generator.py` - strategy generation
- `.agentic-pi/runtime/strategy_memory.py` - strategy memory
- `.agentic-pi/runtime/strategy_applicability_gate.py` - strategy applicability
- `.agentic-pi/runtime/local_step_planner.py` - local step planning
- `.agentic-pi/runtime/milestone_builder.py` - milestone building
- `.agentic-pi/runtime/milestone_proof_runner.py` - milestone proof
- `.agentic-pi/runtime/milestone_tracker.py` - milestone tracking
- `.agentic-pi/runtime/plan_monitor.py` - plan monitoring
- `.agentic-pi/runtime/replan_controller.py` - replan control
- `.agentic-pi/runtime/step_compiler.py` - step compilation
- `.agentic-pi/runtime/checkpoint_writer.py` - checkpoint writing
- `.agentic-pi/runtime/drift_detector.py` - drift detection
- `.agentic-pi/runtime/drift_proof_runner.py` - drift proof
- `.agentic-pi/runtime/experience_extractor.py` - experience extraction
- `.agentic-pi/runtime/experience_retriever.py` - experience retrieval
- `.agentic-pi/runtime/learning_record_writer.py` - learning record writing
- `.agentic-pi/runtime/policy_engine.py` - policy engine
- `.agentic-pi/runtime/strategy_proof_runner.py` - strategy proof
- `.agentic-pi/runtime/strategy_scorer.py` - strategy scoring
- `.agentic-pi/runtime/strategy_selector.py` - strategy selection
- `.agentic-pi/runtime/verifier_provenance.py` - verifier provenance

### Validators

- `.agentic-pi/validators/certifier_gates.py` - certifier gates
- `.agentic-pi/validators/certify_run.py` - certification
- `.agentic-pi/validators/verify_agent_outputs.py` - verification
- `.agentic-pi/validators/validate_memory_contradictions.py` - memory validation
- `.agentic-pi/validators/smell_scanner.py` - smell scanner
- `.agentic-pi/validators/strength_scorer.py` - strength scorer
- `.agentic-pi/validators/validate_delta_plan.py` - delta plan validation
- `.agentic-pi/validators/validate_context_pack.py` - context pack validation
- `.agentic-pi/validators/validate_evidence_freeze.py` - evidence freeze validation
- `.agentic-pi/validators/validate_evidence_index.py` - evidence index validation
- `.agentic-pi/validators/validate_final_status.py` - final status validation
- `.agentic-pi/validators/validate_memory_authority.py` - memory authority validation
- `.agentic-pi/validators/validate_memory_card.py` - memory card validation
- `.agentic-pi/validators/validate_memory_write_gate.py` - memory write gate validation
- `.agentic-pi/validators/validate_quarantine_memory.py` - quarantine memory validation
- `.agentic-pi/validators/validate_run_local_memory.py` - run local memory validation

### Formal Verification

- `.agentic-pi/formal/harness_contract_verifier.py` - contract verification
- `.agentic-pi/formal/harness_signing.py` - cryptographic signing

### Planning

- `.agentic-pi/runtime/roadmap_planner.py` - roadmap planning
- `.agentic-pi/runtime/plan_selector.py` - plan selection
- `.agentic-pi/runtime/plan_merger.py` - plan merging
- `.agentic-pi/runtime/planning_search_tree.py` - search tree
- `.agentic-pi/runtime/planning_coverage.py` - coverage analysis

### Schemas

- `.agentic-pi/schemas/rpg_test_record.schema.json` - test record schema
- `.agentic-pi/schemas/rpg_test_aggregation_result.schema.json` - test aggregation schema
- `.agentic-pi/schemas/final_status.schema.json` - final status schema
- `.agentic-pi/schemas/evidence_index.schema.json` - evidence index schema
- `.agentic-pi/schemas/evidence_freeze.schema.json` - evidence freeze schema
- `.agentic-pi/schemas/evidence_hash_manifest.schema.json` - evidence hash schema
- `.agentic-pi/schemas/run_journal_entry.schema.json` - journal entry schema
- `.agentic-pi/schemas/learning_candidate.schema.json` - learning candidate schema
- `.agentic-pi/schemas/mempalace_card.schema.json` - mempalace card schema
- `.agentic-pi/schemas/context_pack.schema.json` - context pack schema
- `.agentic-pi/schemas/reflection_report.schema.json` - reflection report schema
- `.agentic-pi/schemas/curator_delta.schema.json` - curator delta schema
- `.agentic-pi/schemas/memory_write_decision.schema.json` - memory write decision schema
- `.agentic-pi/schemas/live_negative_prompt_capture_result.schema.json` - negative capture schema
- `.agentic-pi/schemas/real_pi_behavior_evaluation_result.schema.json` - behavior evaluation schema
- `.agentic-pi/schemas/real_pi_behavior_matrix_result.schema.json` - behavior matrix schema
- `.agentic-pi/schemas/runtime_enforcement_result.schema.json` - runtime enforcement schema

### Templates

- `.agentic-pi/templates/rpg_test_record.template.json` - test record template

### Prompts

- `.agentic-pi/prompts/negative_autonomy/` - negative autonomy prompts
- `.agentic-pi/prompts/real_behavior_matrix/` - behavior matrix prompts

### Diagnostics

- `.agentic-pi/diagnostics/pi_real_interactive/` - real interactive diagnostics

### Domain Packs

- `.agentic-pi/domain_packs/` - domain packs

### Proof Matrix

- `.agentic-pi/proof_matrix/proof_matrix.json` - proof matrix

### Evaluation

- `.agentic-pi/evaluation/session_trace_scorer.py` - session trace scoring
- `.agentic-pi/evaluation/tool_use_audit.py` - tool use audit
- `.agentic-pi/evaluation/trajectory_metrics.py` - trajectory metrics

## Current State

The harness is production-ready with:
- Verification system (planning, step, final)
- Context management
- Long-horizon support
- Parallel execution
- Model configuration
- Research module
- Resume mechanism
- Documentation
- Agent integration (Pi tested)
- Health check
- 48 tests

## Version History

- v3.7 = MemPalace + ACE memory governance

## Layers

- Real Pi Agentic Autonomy Probe Layer
- Agentic Negative-Probe Hardening Layer
- Live Negative Prompt Capture Layer
- Real Pi Behavior Evaluation Layer
- Real Pi Prompt Coverage Evaluation Layer
- Runtime Enforcement Proof Layer
- RPG Harness Test Record Layer
- RPG Test Aggregation Layer

## Golden Runs

- raw_simple_historical_compatibility -> DONE_PASS
- raw_p2_provenance -> CERTIFIED_DONE
- raw_missing_verifier -> NOT_DONE

## Flows

- raw goal -> branch candidates -> selected branch -> merged_plan.json
- raw goal -> task type -> capability inventory -> strategy candidates
- raw goal -> selected strategy -> milestone_plan.json -> local_step_plan.json
- raw goal -> worker -> checkpoints -> drift_report.json -> delta_plan.json
- Pi/tool session -> tool_use_audit.json -> trajectory_score.json
- completed run -> experience_extract.json -> learning record -> retrieved_experience.json
- task_type_decision.json -> domain_pack_selection.json -> domain-aware strategy_candidates.json
- domain / memory / trajectory / drift evidence -> workflow_candidates.json -> workflow_search_trace.json
- proof_matrix.json -> run_proof_matrix.py -> proof_matrix_result.json
- verifier-generator -> verifier-reviewer -> goal-orchestrator
- Pi/Mercury session -> verifier evidence -> certifier -> status artifacts
- real `pi` interactive prompt -> Mercury tool use -> pi_chain_runtime_result.json
- captured real Pi transcript -> pi_real_session_monitor.py
- captured real Pi negative-status transcript -> pi_real_session_monitor.py
- real Pi stdout/transcript -> pi_session_trace.jsonl -> pi_session_trace_monitor.py
- negative prompt -> Pi/Mercury trace -> agentic_autonomy_monitor.py -> expected FAIL
- captured negative prompt behavior -> run_real_pi_behavior_evaluation.py -> caught / missed / safe_refusal / inconclusive
- captured prompt matrix -> run_real_pi_behavior_matrix.py -> caught / missed / safe_refusal / inconclusive by category/trial
- Pi/Mercury-shaped command -> command_gateway.py -> protected_file_guard.py
- Pi/Mercury trace -> RPG test record -> regression decision -> deterministic gates
- RPG test records -> rpg_test_aggregator.py -> false-certified / monitor-miss / false-block metrics
- policy_decision.json -> certification.json -> final_status.json -> final_status.md
- trace/logs/artifacts/verifier evidence/policy -> evidence_index.json -> evidence_freeze.json
- current run observation -> memory/*.jsonl -> advisory repair context only
- candidate lesson -> quarantine memory -> not retrievable by future runs
- MemPalace durable card -> context_pack.json -> ACE reflection -> curator delta -> memory_write_gate.py

## Proven Behavior

- prepared historical-compatibility full run through Pi -> DONE_PASS
- prepared provenance full run through Pi -> CERTIFIED_DONE

## Not Proven

- arbitrary raw natural-language autonomy
- full goal-runner.chain.md autonomous runtime
- strict internal Pi tool-call audit for arbitrary live Pi chain smoke
- additional live real Pi weak/failing transcript captures beyond fixtures
- live real Pi trace captures for every status class
- every malicious prompt is classified
- live behavior evaluation on a large adversarial prompt set
- broad real Pi prompt coverage beyond the current bounded matrix
- arbitrary command-gateway bypasses
- statistical proof beyond recorded RPG test records
- live campaign quality beyond collected RPG records
- semantic quality of milestones
- automatic repair application
- deterministic trajectory evaluation
- domain pack quality

## Related Documents

- [V3.5 to V4.0 Authority Evidence Memory Plan](V3_5_TO_V4_0_AUTHORITY_EVIDENCE_MEMORY_PLAN.md)
