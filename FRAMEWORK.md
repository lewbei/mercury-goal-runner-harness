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
v1.2 = Planning Proof Hardening
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

It does not prove arbitrary natural-language autonomy.

## Conceptual Architecture

```text
Raw Goal
  -> Goal Contract
  -> Verifier Contract
  -> PlanGraph
  -> Guarded Worker
  -> Artifacts
  -> Verifier Artifacts
  -> Smell Scanner
  -> Strength Scorer
  -> Policy Engine
  -> Certifier
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

4. Planning Layer
   Builds plan and artifact-linked graph views. Plans do not certify DONE.

5. Execution Layer
   Guarded Worker executes approved steps and writes artifacts inside the run
   folder.

6. Artifact Layer
   Stores produced outputs. Artifacts are checked; they are not trusted because
   they exist.

7. Verifier Provenance Layer
   Records who produced verifier evidence, when it was produced, and whether it
   is independent from the solution.

8. Verifier Quality Layer
   Smell scanner and strength scorer classify weak, advisory, gating, and
   certifying evidence.

9. Policy Layer
   Policy engine decides NOT_DONE, PROVISIONAL_DONE, or CERTIFIED_DONE in
   provenance mode.

10. Certifier Layer
    Certifier writes certification.json and final_status.md.

11. Pi Report Layer
    Pi can orchestrate and report, but cannot certify DONE by itself.
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
.agentic-pi/runtime/pi_cli.py
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

.agentic-pi/validators/certify_run.py
.agentic-pi/validators/smell_scanner.py
.agentic-pi/validators/strength_scorer.py
.agentic-pi/validators/validate_plan_graph.py
.agentic-pi/validators/validate_schema.py

.agentic-pi/diagnostics/provenance_gate/
.agentic-pi/diagnostics/evaluation/
.agentic-pi/diagnostics/host_integration/
.agentic-pi/diagnostics/pi_command_discipline/

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
live Mercury planning quality
semantic optimality of selected branches
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
python -m unittest discover tests -v
python .agentic-pi\diagnostics\evaluation\run_diagnostic_evaluation.py
python .agentic-pi\benchmark\run_benchmark.py
python .agentic-pi\runtime\pi_cli.py --help
python .agentic-pi\runtime\pi_cli.py goal-compile pi_smoke_planning_proof_p2 --goal "Create README.md explaining the harness" --mode planning_p2
python .agentic-pi\runtime\pi_cli.py goal-plan-proof pi_smoke_planning_proof_p2
```

## One-Line Framework

```text
Raw Goal
  -> Goal Contract
  -> Verifier Contract
  -> PlanGraph
  -> Guarded Worker
  -> Artifacts
  -> Verifier Artifacts
  -> Smell Scanner
  -> Strength Scorer
  -> Policy Engine
  -> Certifier
  -> Audit / Replay
  -> Final Status
  -> Pi Reports Status Only
```
