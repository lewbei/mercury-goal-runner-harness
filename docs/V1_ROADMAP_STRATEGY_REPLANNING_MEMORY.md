# v1 Roadmap: Strategy, Replanning, Memory, Evaluation, Domain Packs, Search

This roadmap preserves the research-informed middle layer without weakening the certification invariant:

```text
Who is allowed to certify DONE?
Strategy can suggest.
Planner can select.
Memory can suggest.
Domain packs can suggest.
Workflow search can rank.
Proof matrix can report.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

v1.3 starts the middle layer. The later items below are not implemented in v1.3 unless explicitly marked.

## v1.3 Universal / Domain-Aware Strategy Planner

Status:

```text
IMPLEMENTED
```

Purpose:

```text
raw goal
-> task type
-> capability inventory
-> strategy candidates
-> applicability gate
-> strategy scorer
-> selected strategy
-> step compiler
-> merged_plan.json
-> worker
-> certifier
```

Macro steps:

1. Route task type from deterministic goal-contract signals.
2. Record current harness capabilities.
3. Generate strategy candidates by task type.
4. Gate candidates against missing capabilities and forbidden authority claims.
5. Score candidates by certifiability, artifact tests, risk, and fit.
6. Select a deterministic strategy.
7. Compile strategy into `merged_plan.json`.
8. Execute through the existing worker/certifier path.

Boundary:

```text
Strategy artifacts cannot certify DONE.
```

## v1.4 Milestone Planning

Status:

```text
IMPLEMENTED
```

Purpose:

```text
Selected Strategy
-> Milestone Plan
-> Local Step Plan
-> Step Compiler
```

Macro steps:

1. Add `milestone_builder.py`.
2. Define milestone plans for coding, research, writing, debugging, benchmark, and experiment tasks.
3. Add `milestone_tracker.py` with `planned`, `active`, `complete`, and `blocked`.
4. Add `local_step_planner.py`.
5. Make `step_compiler.py` consume local step plans when present.
6. Keep the legacy strategy-only compile path working.

Acceptance:

```text
milestones preserve long-horizon structure
local steps preserve milestone order
certifier remains final authority
```

Implemented proof command:

```cmd
python .agentic-pi\runtime\pi_cli.py goal-milestone-proof <run_id>
```

## v1.5 Drift-Aware Replanning

Status:

```text
IMPLEMENTED
```

Purpose:

```text
Step executes
-> checkpoint
-> drift detector
-> if OK continue
-> if drift pause
-> drift_report.json
-> delta plan
-> policy gate
-> continue / rollback / abort
```

Macro steps:

1. Add checkpoint writer.
2. Add plan monitor.
3. Add drift detector with `none`, `minor`, `repairable`, and `fatal`.
4. Add replan controller.
5. Add delta plan validator.
6. Connect fatal drift to rollback dry-run.

Acceptance:

```text
worker status-artifact writes are fatal drift
worker verifier_artifacts writes are fatal drift
delta plans cannot bypass policy
rollback remains dry-run by default
```

Implemented proof command:

```cmd
python .agentic-pi\runtime\pi_cli.py goal-drift-proof <run_id>
```

## v1.6 Trajectory-Level Evaluation

Status:

```text
IMPLEMENTED
```

Purpose:

```text
Did the agent use the right tool, with the right arguments, in the right order?
```

Macro steps:

1. Add trajectory metrics.
2. Add tool-use audit.
3. Add session trace scorer.
4. Add diagnostic cases for duplicate calls, manual writes, missing reads, unsafe deletion, and wrong order.
5. Add trajectory metrics to diagnostic reports.

Acceptance:

```text
trajectory scorer can fail unsafe behavior
trajectory scorer cannot certify DONE
policy/certifier remain final authority
```

Implemented proof command:

```cmd
python .agentic-pi\diagnostics\trajectory_evaluation\run_trajectory_evaluation.py
```

## v1.7 Experience Memory

Status:

```text
IMPLEMENTED
```

Purpose:

```text
completed run
-> extract failure/success pattern
-> write learning record
-> retrieve relevant strategy principle next run
-> strategy planner may use it
-> certifier still decides
```

Macro steps:

1. Add experience extractor.
2. Add append-only learning record writer.
3. Add deterministic strategy memory.
4. Add experience retriever.
5. Let strategy scorer consume retrieved experience as advisory evidence only.

Acceptance:

```text
memory can suggest
memory cannot write final_status.md
memory cannot certify DONE
memory cannot bypass applicability gate
```

Implemented proof command:

```cmd
python tests\test_experience_memory.py -v
```

## v1.8 Domain Packs

Status:

```text
IMPLEMENTED
```

Purpose:

```text
Make strategy generation domain-aware without claiming one generic planner handles everything equally well.
```

Domain packs:

```text
coding
research
writing
debugging
experiment
benchmark
devops
```

Macro steps:

1. Define domain pack schema.
2. Add coding pack.
3. Add research pack.
4. Add writing pack.
5. Add benchmark pack.
6. Add debugging, experiment, and devops packs.
7. Add domain pack selector.
8. Let selected packs shape strategy candidates.
9. Leave unknown domains as `NEED_USER_DOMAIN`.

Acceptance:

```text
domain packs affect strategy candidates
domain packs cannot certify DONE
unknown goals do not guess unsafe packs
```

Implemented proof command:

```cmd
python tests\test_domain_packs.py -v
```

## v1.9 Strategy Search / Workflow Optimization

Status:

```text
IMPLEMENTED
```

Purpose:

```text
Search over strategy/workflow candidates after trajectory metrics and memory exist.
```

Macro steps:

1. Add workflow candidate model.
2. Add lightweight workflow search.
3. Score workflows using trajectory score, false-certified risk, cost, verifier strength, drift history, domain packs, and experience memory.
4. Write `workflow_search_trace.json`.
5. Reject workflows that bypass certifier or hide failed checks.
6. Keep selected workflow execution deferred.

Acceptance:

```text
workflow search cannot bypass certifier
rejected workflows have reasons
fixed pipeline still works
```

Implemented proof command:

```cmd
python tests\test_workflow_search.py -v
```

## v2.0 Integrated Harness Proof Package

Status:

```text
IMPLEMENTED
```

Purpose:

```text
Freeze a usable, inspectable harness with all proven layers connected.
```

Macro steps:

1. Add proof matrix.
2. Add one-command proof runner.
3. Add release docs.
4. Add example set for `DONE_PASS`, `PROVISIONAL_DONE`, `CERTIFIED_DONE`, `NOT_DONE`, drift detection, trajectory failure, memory suggestion, and domain pack selection.
5. Add workflow-search example.
6. Add package sanity checks.

Acceptance:

```text
full proof matrix passes
false CERTIFIED_DONE remains zero on diagnostic set
docs separate tested behavior from untested behavior
full Pi autonomy is not claimed unless separately proven
```

Implemented proof command:

```cmd
python .agentic-pi\runtime\run_proof_matrix.py --mode quick
```

## v2.1 Controlled Pi Chain Runtime Proof

Status:

```text
IMPLEMENTED
```

Purpose:

```text
verifier-generator
-> verifier-reviewer
-> goal-orchestrator
-> certifier-owned status artifacts
```

Macro steps:

1. Add a controlled Pi chain smoke runner.
2. Keep verifier-generator and verifier-reviewer read-only.
3. Restrict goal-orchestrator to the deterministic certifier command.
4. Read `final_status.md`, `certification.json`, and `policy_decision.json` directly after Pi exits.
5. Record `final_status_authority = certifier_only`.
6. Record `can_certify_done = false`.

Acceptance:

```text
controlled Pi chain smoke is bounded
status artifacts remain certifier-owned
full arbitrary Pi chain autonomy remains unclaimed
```

Implemented proof command:

```cmd
python .agentic-pi\runtime\run_pi_chain_smoke.py --target-run-id pi_smoke_chain_p2_strong
```

## v2.2 Direct Pi/Mercury Behavior Audit

Status:

```text
IMPLEMENTED
```

Purpose:

```text
Pi is the CLI/harness surface.
Mercury is the LLM behavior inside Pi.
```

This slice audits whether a Pi/Mercury session follows verifier-provenance
order:

```text
verifier evidence
-> certifier invocation
-> certifier-owned status artifacts
```

Macro steps:

1. Add direct behavior session fixtures.
2. Require `goal_contract.json`, `verifier_contract.json`, and `verifier_artifacts/*` reads before certification.
3. Require exactly one `certify_run.py` invocation.
4. Require `final_status.md`, `certification.json`, and `policy_decision.json` reads after certification.
5. Reject self-certifying assistant language.
6. Keep `final_status_authority = certifier_only`.
7. Keep `can_certify_done = false`.

Acceptance:

```text
verifier evidence before certifier invocation
status artifacts after certifier invocation
Pi/Mercury cannot certify DONE by itself
arbitrary live Pi autonomy remains unclaimed
```

Implemented proof command:

```cmd
python tests\test_pi_direct_behavior_audit.py -v
```

## v2.3 Real Pi Interactive Smoke Evidence

Status:

```text
RECORDED
```

Purpose:

```text
Record one real `pi` interactive session where Mercury follows the
verifier-provenance reporting contract.
```

Macro steps:

1. Launch the real Pi agent from cmd with `pi`.
2. Paste the single-action v2.3 prompt.
3. Require exactly one controlled smoke command.
4. Require reading `pi_chain_runtime_result.json`.
5. Require reporting only artifact values.
6. Keep `final_status_authority = certifier_only`.
7. Keep `can_certify_done = false`.

Acceptance:

```text
result_status: PASS
status_artifacts_agree: true
final_status_authority: certifier_only
can_certify_done: false
local smoke evidence, not automated CI evidence
```

Implemented documentation check:

```cmd
python tests\test_pi_real_interactive_smoke_docs.py -v
```

## Research Anchor Mapping

```text
Tool-learning surveys -> task planning + tool/capability selection
HiPlan -> milestone/global-local planning
ALAS -> transactional logs, checkpoints, localized repair, rollback/retry discipline
TRAJECT-Bench -> trajectory-level tool-use metrics
EvolveR -> experience lifecycle memory
AFlow -> later workflow search
Agent evaluation survey -> multi-dimensional agent metrics
SWE-rebench -> coding-agent benchmark contamination caution
```
