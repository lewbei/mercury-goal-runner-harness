# Verifier-Provenance Goal Runner Harness Framework

This file is the framework source of truth for the current architecture.

It separates:

```text
conceptual architecture
actual current repo file map
```

That distinction matters. A clean framework is useful, but the repo should not
claim folders, tools, or autonomous runtime behavior that are not actually
implemented.

## Core Question

```text
Who is allowed to certify DONE?
```

Core invariant:

```text
Agents do work.
Verifiers produce evidence.
Policy engine judges the evidence.
Certifier writes the final status.
Pi only reports what the certifier wrote.
```

## Current Implemented State

Current pushed state:

```text
v2.7 = Real Pi Agentic Autonomy Probe
```

The deterministic raw-goal proof cases are:

```text
raw_simple_legacy -> DONE_PASS
raw_p2_provenance -> CERTIFIED_DONE
raw_missing_verifier -> NOT_DONE
```

The current system proves a narrow but important path:

```text
raw goal -> goal_contract.json -> full harness run -> certifier status
```

v1.2 also proves the deterministic planning handoff:

```text
raw goal -> branch candidates -> selected branch -> merged_plan.json -> worker -> certifier status
```

v1.3 adds deterministic strategy selection before step compilation:

```text
raw goal -> task type -> capability inventory -> strategy candidates -> applicability gate -> strategy score -> selected strategy -> step compiler -> merged_plan.json -> worker -> certifier status
```

v1.4 adds milestone planning between selected strategy and local executable steps:

```text
raw goal -> selected strategy -> milestone_plan.json -> local_step_plan.json -> merged_plan.json -> worker -> certifier status
```

v1.5 adds drift detection after worker execution and before certification:

```text
raw goal -> worker -> checkpoints -> drift_report.json -> delta_plan.json -> certifier status
```

v1.6 adds trajectory-level tool-use evaluation:

```text
Pi/tool session -> tool_use_audit.json -> trajectory_score.json -> diagnostic report
```

v1.7 adds advisory experience memory:

```text
completed run -> experience_extract.json -> learning record -> retrieved_experience.json -> strategy score adjustment
```

v1.8 adds deterministic domain packs:

```text
task_type_decision.json -> domain_pack_selection.json -> domain-aware strategy_candidates.json
```

v1.9 adds deterministic workflow search:

```text
domain / memory / trajectory / drift evidence -> workflow_candidates.json -> workflow_search_trace.json
```

v2.0 adds an integrated proof matrix:

```text
proof_matrix.json -> run_proof_matrix.py -> proof_matrix_result.json
```

v2.1 adds a controlled Pi chain smoke:

```text
verifier-generator -> verifier-reviewer -> goal-orchestrator -> certifier-owned status artifacts
```

It does not prove arbitrary natural-language autonomy or full Pi chain autonomy.

v2.2 adds a direct Pi/Mercury behavior audit:

```text
Pi/Mercury session -> verifier evidence -> certifier -> status artifacts
```

This proves the session order can be audited. It does not prove Mercury semantic
quality or arbitrary live Pi autonomy.

v2.3 records a real Pi interactive smoke:

```text
real `pi` interactive prompt -> Mercury tool use -> pi_chain_runtime_result.json -> artifact-only report
```

This is local smoke evidence, not automated CI evidence. It does not prove
arbitrary Pi autonomy or full goal-runner.chain.md runtime.

v2.4 monitors captured real Pi interactive transcripts:

```text
captured real Pi transcript -> pi_real_session_monitor.py -> command/read trajectory verdict
```

This checks how Pi ran the smoke, not only what final result it reported.

v2.5 extends the real Pi transcript monitor to weak and failing statuses:

```text
captured real Pi negative-status transcript -> pi_real_session_monitor.py -> status-upgrade verdict
```

This checks that `PROVISIONAL_DONE` and `NOT_DONE` are reported from
certifier-owned artifacts and not upgraded by Mercury.

v2.6 normalizes captured Pi output into a session trace:

```text
real Pi stdout/transcript -> pi_session_trace.jsonl -> pi_session_trace_monitor.py
```

This makes the trace log the auditable source of truth for command/read/report discipline.

v2.7 runs and monitors a real Pi/Mercury agentic autonomy probe:

```text
real Pi -> chain read -> advisory memory read -> first certifier NOT_DONE -> run-local repair -> second certifier CERTIFIED_DONE -> status artifact report -> agentic_autonomy_monitor.py
```

This proves a bounded monitored repair path on a disposable run. It does not prove that arbitrary unbounded bash or arbitrary goal-runner.chain.md autonomy is safe.

## Conceptual Architecture

```text
Raw Goal
  -> Goal Contract
  -> Verifier Contract
  -> Task Type Router
  -> Domain Pack Selector
  -> Capability Inventory
  -> Strategy Candidates
  -> Applicability Gate
  -> Strategy Scorer
  -> Selected Strategy
  -> Milestone Plan
  -> Local Step Plan
  -> Step Compiler
  -> PlanGraph
  -> Guarded Worker
  -> Checkpoints
  -> Drift Detector
  -> Delta Plan
  -> Artifacts
  -> Verifier Artifacts
  -> Smell Scanner
  -> Strength Scorer
  -> Policy Engine
  -> Certifier
  -> Trajectory Evaluation
  -> Experience Memory
  -> Domain Packs
  -> Workflow Search
  -> Proof Matrix
  -> Controlled Pi Chain Smoke
  -> Direct Pi/Mercury Behavior Audit
  -> Real Pi Interactive Smoke
  -> Real Pi Run Monitor
  -> Real Pi Negative-Status Smoke Monitor
  -> Real Pi Session Trace Capture
  -> Real Pi Agentic Autonomy Probe
  -> Audit / Replay
  -> Final Status
  -> Pi Reports Status Only
```

## Layer Responsibilities

```text
1. Raw Goal Compiler
   Converts a raw goal string into deterministic fixture contracts.

2. Goal Contract
   Defines final outputs, done criteria, failure criteria, constraints, and
   allowed scope.

3. Verifier Contract
   Defines what evidence is required before final certification.

4. Strategy Layer
   Routes task type, records capabilities, generates strategy candidates,
   gates unsafe strategies, scores candidates, selects one strategy, and
   prepares the selected strategy. Strategies do not certify DONE.

5. Milestone Layer
   Expands the selected strategy into milestone_plan.json, records local
   milestone statuses, and lowers milestones into local_step_plan.json.
   Milestones do not certify DONE.

6. Planning Layer
   Builds plan and artifact-linked graph views. Plans do not certify DONE.

7. Execution Layer
   Guarded Worker executes approved steps and writes artifacts inside the run
   folder.

8. Drift Layer
   Writes checkpoints, compares execution against merged_plan.json, records
   drift_report.json, and creates bounded delta_plan.json for repairable drift.
   Drift reports can block certification, but cannot certify DONE.

9. Artifact Layer
   Stores produced outputs. Artifacts are checked; they are not trusted because
   they exist.

10. Verifier Provenance Layer
   Records who produced verifier evidence, when it was produced, and whether it
   is independent from the solution.

11. Verifier Quality Layer
   Smell scanner and strength scorer classify weak, advisory, gating, and
   certifying evidence.

12. Policy Layer
   Policy engine decides NOT_DONE, PROVISIONAL_DONE, or CERTIFIED_DONE in
   provenance mode.

13. Certifier Layer
    Certifier writes certification.json and final_status.md.

14. Trajectory Evaluation Layer
    Scores tool selection, tool arguments, tool order, duplicate certifier
    invocations, missing status reads, manual status writes, and unsafe tool
    attempts. Trajectory evaluators can fail unsafe behavior, but cannot
    certify DONE.

15. Pi Report Layer
    Pi can orchestrate and report, but cannot certify DONE by itself.
    The real Pi agent is launched by typing `pi` in a terminal. The repo-local
    `.agentic-pi/runtime/pi_cli.py` file is only a deterministic harness helper,
    not the Pi agent.

16. Experience Memory Layer
    Extracts reusable strategy lessons, writes append-only learning records,
    retrieves matching principles, and adjusts strategy scores. Memory can
    suggest, but cannot certify DONE or bypass applicability gates.

17. Domain Pack Layer
    Selects deterministic task-domain packs for coding, research, writing,
    debugging, experiment, benchmark, and devops tasks. Domain packs can shape
    strategy candidates and verifier hints, but cannot certify DONE or bypass
    the policy engine.

18. Workflow Search Layer
    Generates and scores deterministic workflow candidates using trajectory,
    drift, memory, domain-pack, risk, and cost evidence. Workflow search can
    rank workflows, but cannot execute them or certify DONE.

19. Proof Matrix Layer
    Maps implementation claims to commands, expected evidence, and claim
    boundaries. The proof matrix can report pass/fail evidence, but cannot
    certify DONE.

20. Controlled Pi Chain Smoke Layer
    Runs or plans a bounded verifier-generator -> verifier-reviewer ->
    goal-orchestrator smoke on disposable `pi_smoke_*` runs. The smoke runner
    can report Pi-process evidence, but cannot certify DONE.

21. Direct Pi/Mercury Behavior Audit Layer
    Audits synthetic Pi/Mercury session traces for verifier evidence reads
    before certifier invocation, status reads after certifier invocation, and
    no self-certifying assistant language. The audit can fail unsafe behavior,
    but cannot certify DONE.

22. Real Pi Interactive Smoke Layer
    Records local evidence from a real `pi` interactive session where Mercury
    invoked the controlled smoke command, read pi_chain_runtime_result.json,
    and reported only certifier-owned artifact values. This is local smoke
    evidence, not automated CI evidence, and cannot certify DONE.

23. Real Pi Run Monitor Layer
    Parses captured real Pi interactive transcript fixtures and checks exactly
    one allowed bash command, required result reads after that command, no
    write/edit/apply_patch use, no protected status writes, and no
    self-certifying assistant language. The monitor can fail unsafe behavior,
    but cannot certify DONE.

24. Real Pi Negative-Status Smoke Monitor Layer
    Uses the same real Pi transcript monitor for `PROVISIONAL_DONE` and
    `NOT_DONE` cases. It accepts weak or failing statuses when all
    certifier-owned artifacts agree, and rejects assistant-side upgrades such
    as `PROVISIONAL_DONE` to `CERTIFIED_DONE`.

25. Real Pi Session Trace Capture Layer
    Converts captured Pi output into `pi_session_trace.jsonl` and audits that
    normalized trace for exactly-one-command discipline, required reads,
    certifier-only status authority, and no assistant-side status upgrades.
    The trace monitor can fail unsafe behavior, but cannot certify DONE.

26. Real Pi Agentic Autonomy Probe Layer
    Runs a real Pi/Mercury probe on a disposable run, requires the chain
    contract and advisory memory to be read, starts from an initial certifier
    failure, allows one run-local artifact repair, reruns the certifier, and
    monitors the resulting trace. It proves a bounded repair path only; it
    cannot prove arbitrary unbounded bash or arbitrary chain autonomy is safe.
```

## Authority Model

```text
P0 = self-authored verifier
     Advisory only.

P1 = visible/local verifier
     Can gate progress, but provisional by default.

P2 = independent audited verifier
     Can certify if verifier strength is certifying.

P3 = hidden/user/external verifier
     Strongest authority.
```

Decision table:

```text
Target artifact missing                  -> NOT_DONE
Verifier contract exists, no verifier    -> NOT_DONE
P0 only                                  -> PROVISIONAL_DONE
P1 only                                  -> PROVISIONAL_DONE
P2/P3 with weak/advisory/gating strength -> PROVISIONAL_DONE
P2/P3 with certifying strength           -> CERTIFIED_DONE
```

Main policy:

```text
P0 alone cannot certify DONE.
```

## Actual Current Repo File Map

The current repo does not use separate `policy/`, `planning/`, or `provenance/`
top-level folders. The implemented files are:

```text
.agentic-pi/runtime/compile_raw_goal.py
.agentic-pi/runtime/planning_proof_runner.py
.agentic-pi/runtime/task_type_router.py
.agentic-pi/runtime/domain_pack_selector.py
.agentic-pi/runtime/workflow_search.py
.agentic-pi/runtime/run_proof_matrix.py
.agentic-pi/runtime/run_pi_chain_smoke.py
.agentic-pi/runtime/capability_inventory.py
.agentic-pi/runtime/strategy_generator.py
.agentic-pi/runtime/strategy_applicability_gate.py
.agentic-pi/runtime/strategy_scorer.py
.agentic-pi/runtime/strategy_selector.py
.agentic-pi/runtime/milestone_builder.py
.agentic-pi/runtime/milestone_tracker.py
.agentic-pi/runtime/local_step_planner.py
.agentic-pi/runtime/step_compiler.py
.agentic-pi/runtime/strategy_proof_runner.py
.agentic-pi/runtime/milestone_proof_runner.py
.agentic-pi/runtime/checkpoint_writer.py
.agentic-pi/runtime/plan_monitor.py
.agentic-pi/runtime/drift_detector.py
.agentic-pi/runtime/replan_controller.py
.agentic-pi/runtime/drift_proof_runner.py
.agentic-pi/runtime/experience_extractor.py
.agentic-pi/runtime/learning_record_writer.py
.agentic-pi/runtime/strategy_memory.py
.agentic-pi/runtime/experience_retriever.py
.agentic-pi/runtime/pi_cli.py  # repo-local harness helper, not external Pi
.agentic-pi/runtime/run_goal.py
.agentic-pi/runtime/write_goal_contract.py
.agentic-pi/runtime/plan_router.py
.agentic-pi/runtime/plan_selector.py
.agentic-pi/runtime/plan_merger.py
.agentic-pi/runtime/plan_graph_builder.py
.agentic-pi/runtime/artifact_linker.py
.agentic-pi/runtime/task_graph_builder.py
.agentic-pi/runtime/guarded_worker.py
.agentic-pi/runtime/verifier_provenance.py
.agentic-pi/runtime/policy_engine.py
.agentic-pi/runtime/audit_run.py
.agentic-pi/runtime/replay_run.py
.agentic-pi/runtime/rollback_run.py
.agentic-pi/runtime/setup_pi_smoke.py
.agentic-pi/runtime/pi_session_audit.py
.agentic-pi/runtime/pi_direct_behavior_audit.py
.agentic-pi/runtime/pi_real_session_monitor.py
.agentic-pi/runtime/pi_session_trace_monitor.py
.agentic-pi/runtime/run_real_pi_trace_smoke.py

.agentic-pi/evaluation/trajectory_metrics.py
.agentic-pi/evaluation/tool_use_audit.py
.agentic-pi/evaluation/session_trace_scorer.py

.agentic-pi/validators/certify_run.py
.agentic-pi/validators/smell_scanner.py
.agentic-pi/validators/strength_scorer.py
.agentic-pi/validators/validate_plan_graph.py
.agentic-pi/validators/validate_delta_plan.py
.agentic-pi/validators/validate_schema.py

.agentic-pi/diagnostics/provenance_gate/
.agentic-pi/diagnostics/evaluation/
.agentic-pi/diagnostics/host_integration/
.agentic-pi/diagnostics/pi_command_discipline/
.agentic-pi/diagnostics/pi_direct_behavior/
.agentic-pi/diagnostics/pi_real_interactive/
.agentic-pi/diagnostics/trajectory_evaluation/

.agentic-pi/evaluation/trajectory_metrics.py
.agentic-pi/evaluation/tool_use_audit.py
.agentic-pi/evaluation/session_trace_scorer.py

.agentic-pi/memory/learning_records/

.agentic-pi/domain_packs/
.agentic-pi/proof_matrix/proof_matrix.json

.pi/agents/goal-orchestrator.md
.pi/agents/verifier-generator.md
.pi/agents/verifier-reviewer.md
.pi/chains/goal-runner.chain.md
```

## Run Folder Contract

Typical run folder:

```text
.agentic-runs/<run_id>/
  goal_contract.json
  verifier_contract.json
  plan_graph.json
  artifact_registry.json
  task_graph.json
  step_logs/
  trace.jsonl
  artifacts/
  verifier_artifacts/
  verifier_smell_reports/
  verifier_strength_reports/
  policy_decision.json
  certification.json
  final_status.md
  run_manifest.json
  audit_report.json
  replay_report.json
  rollback_report.json
```

Important compatibility rule:

```text
policy_decision.json exists only in provenance mode.
```

Legacy runs without `verifier_contract.json` use:

```text
DONE_PASS
DONE_FAIL
```

Provenance-mode runs use:

```text
NOT_DONE
PROVISIONAL_DONE
CERTIFIED_DONE
```

## Pi Integration Boundary

Pi agents and chains are prompt/runtime contracts:

```text
.pi/agents/goal-orchestrator.md
.pi/agents/verifier-generator.md
.pi/agents/verifier-reviewer.md
.pi/chains/goal-runner.chain.md
```

Allowed:

```text
Pi can orchestrate.
Pi can invoke deterministic harness commands.
Pi can read final_status.md, certification.json, and policy_decision.json.
Pi can report what those files say.
```

Not allowed:

```text
Pi cannot certify DONE by itself.
Pi cannot manually edit final_status.md.
Pi cannot manually edit certification.json.
Pi cannot manually edit policy_decision.json.
Pi cannot forge verifier_artifacts/.
```

## Proven Behavior

Currently proven:

```text
prepared legacy full run through Pi -> DONE_PASS
prepared provenance full run through Pi -> CERTIFIED_DONE
deterministic raw-goal legacy fixture -> DONE_PASS
deterministic raw-goal P2 fixture -> CERTIFIED_DONE
deterministic raw-goal missing verifier fixture -> NOT_DONE
deterministic planning proof fixture -> selected branch -> merged_plan.json -> CERTIFIED_DONE
deterministic strategy proof fixture -> selected strategy -> merged_plan.json -> CERTIFIED_DONE
deterministic milestone proof fixture -> milestone_plan.json -> local_step_plan.json -> merged_plan.json -> CERTIFIED_DONE
deterministic drift proof fixture -> drift_report.json none -> CERTIFIED_DONE
deterministic trajectory evaluation -> duplicate/manual/missing/unsafe/wrong-order cases fail
deterministic experience memory -> success/failure/provisional lessons affect strategy score but do not certify
deterministic domain packs -> task type selects pack -> strategy candidates receive advisory domain hints
deterministic workflow search -> unsafe/high-risk workflows rejected -> selected workflow preserves certifier authority
integrated proof matrix -> bounded proof commands -> proof_matrix_result.json
controlled Pi chain smoke -> verifier-generator -> verifier-reviewer -> goal-orchestrator
direct Pi/Mercury behavior audit -> verifier evidence before certifier -> status reads after certifier
real Pi interactive smoke -> controlled prompt -> pi_chain_runtime_result.json -> artifact-only report
real Pi run monitor -> captured transcript -> command/read trajectory verdict
real Pi negative-status monitor -> PROVISIONAL_DONE/NOT_DONE transcript fixtures -> no status upgrade
real Pi session trace capture -> pi_session_trace.jsonl -> trace monitor verdict
real Pi agentic autonomy probe -> chain/memory read -> repair loop -> certifier-only status verdict
P0/P1/P2/missing verifier policy behavior
smell report recording
strength report recording
policy_decision.json enforcement
audit/replay validation
rollback dry-run and protected target rejection
Pi command-discipline audit fixtures
small diagnostic evaluation false CERTIFIED_DONE rate = 0 on fixture set
benchmark status matching with false PASS reporting
```

## Not Proven

Not proven yet:

```text
arbitrary raw natural-language autonomy
full goal-runner.chain.md autonomous runtime
strict internal Pi tool-call audit for arbitrary live Pi chain smoke
additional live real Pi weak/failing transcript captures beyond fixtures
live real Pi trace captures for every status class
global Pi extension compatibility during Pi chain smoke
live Mercury planning quality
semantic optimality of selected branches
semantic optimality of selected strategies
semantic quality of milestones
automatic repair application
domain pack quality
workflow-search execution integration
workflow-search semantic optimality
full proof matrix mode runtime on every machine
automatic verifier generation
SWE-bench integration
OpenHands integration
large benchmark validity
model routing
long-term memory quality
dashboard workflow
```

## Proof Commands

```cmd
python tests\test_raw_goal_chain.py -v
python tests\test_planning_proof_hardening.py -v
python tests\test_strategy_planner.py -v
python tests\test_milestone_planning.py -v
python tests\test_drift_replanning.py -v
python tests\test_trajectory_evaluation.py -v
python tests\test_experience_memory.py -v
python tests\test_domain_packs.py -v
python tests\test_workflow_search.py -v
python tests\test_v2_proof_package.py -v
python tests\test_pi_chain_runtime_proof.py -v
python tests\test_pi_direct_behavior_audit.py -v
python tests\test_pi_real_interactive_smoke_docs.py -v
python tests\test_pi_real_session_monitor.py -v
python tests\test_pi_session_trace_capture.py -v
python .agentic-pi\runtime\run_proof_matrix.py --mode quick
python .agentic-pi\runtime\run_pi_chain_smoke.py --target-run-id pi_smoke_chain_p2_strong
python -m unittest discover tests -v
python .agentic-pi\diagnostics\evaluation\run_diagnostic_evaluation.py
python .agentic-pi\diagnostics\trajectory_evaluation\run_trajectory_evaluation.py
python .agentic-pi\benchmark\run_benchmark.py
python .agentic-pi\runtime\pi_cli.py --help
python .agentic-pi\runtime\pi_cli.py goal-compile pi_smoke_planning_proof_p2 --goal "Create README.md explaining the harness" --mode planning_p2
python .agentic-pi\runtime\pi_cli.py goal-plan-proof pi_smoke_planning_proof_p2
python .agentic-pi\runtime\pi_cli.py goal-compile pi_smoke_strategy_proof_p2 --goal "Create README.md explaining the harness" --mode p2
python .agentic-pi\runtime\pi_cli.py goal-strategy-proof pi_smoke_strategy_proof_p2
python .agentic-pi\runtime\pi_cli.py goal-compile pi_smoke_milestone_proof_p2 --goal "Create README.md explaining the harness" --mode p2
python .agentic-pi\runtime\pi_cli.py goal-milestone-proof pi_smoke_milestone_proof_p2
python .agentic-pi\runtime\pi_cli.py goal-compile pi_smoke_drift_proof_p2 --goal "Create README.md explaining the harness" --mode p2
python .agentic-pi\runtime\pi_cli.py goal-drift-proof pi_smoke_drift_proof_p2
```

## One-Line Framework

```text
Raw Goal
  -> Goal Contract
  -> Task Type Router
  -> Domain Pack Selector
  -> Capability Inventory
  -> Strategy Selector
  -> Milestone Plan
  -> Local Step Plan
  -> Step Compiler
  -> Verifier Contract
  -> PlanGraph
  -> Guarded Worker
  -> Drift Detector
  -> Artifacts
  -> Verifier Artifacts
  -> Smell Scanner
  -> Strength Scorer
  -> Policy Engine
  -> Certifier
  -> Trajectory Evaluation
  -> Experience Memory
  -> Domain Packs
  -> Workflow Search
  -> Proof Matrix
  -> Controlled Pi Chain Smoke
  -> Audit / Replay
  -> Final Status
  -> Pi Reports Status Only
```
