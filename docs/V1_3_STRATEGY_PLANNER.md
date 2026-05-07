# v1.3 Strategy Planner

## STRATEGY PLANNER IMPLEMENTED

v1.3 adds the first deterministic universal / domain-aware strategy planner slice.

The core invariant stays unchanged:

```text
Who is allowed to certify DONE?
Strategy can suggest.
Planner can select.
Worker can execute.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

## Proof Path

The implemented path is:

```text
raw goal
  -> task type
  -> capability inventory
  -> strategy candidates
  -> applicability gate
  -> strategy score
  -> selected strategy
  -> step compiler
  -> merged_plan.json
  -> worker
  -> certifier
```

The CLI command is:

```cmd
python .agentic-pi\runtime\pi_cli.py goal-strategy-proof <run_id>
```

It expects an existing run folder with `goal_contract.json` and optional `verifier_contract.json`.

## Implemented Files

```text
.agentic-pi/runtime/task_type_router.py
.agentic-pi/runtime/capability_inventory.py
.agentic-pi/runtime/strategy_generator.py
.agentic-pi/runtime/strategy_applicability_gate.py
.agentic-pi/runtime/strategy_scorer.py
.agentic-pi/runtime/strategy_selector.py
.agentic-pi/runtime/step_compiler.py
.agentic-pi/runtime/strategy_proof_runner.py
```

Schemas:

```text
.agentic-pi/schemas/task_type_decision.schema.json
.agentic-pi/schemas/capability_inventory.schema.json
.agentic-pi/schemas/strategy_candidate.schema.json
.agentic-pi/schemas/strategy_decision.schema.json
```

## Task Types

The router classifies deterministic fixture goals as:

```text
coding
research
writing
debugging
experiment
benchmark
unknown
```

Routing is intentionally simple and deterministic. It uses signals from `goal_contract.json`; it does not claim semantic understanding of arbitrary user goals.

## Strategy Candidates

Initial strategy IDs:

```text
S.WRITE_SIMPLE
S.CODE_ARTIFACT_TEST
S.RESEARCH_SOURCE_AUDIT
S.DEBUG_REPRO_THEN_PATCH
S.BENCHMARK_DIAGNOSTIC
S.UNKNOWN_NEED_USER
```

Strategies are planning artifacts only. They cannot certify DONE, write status artifacts, or forge verifier evidence.

## Applicability Gate

The gate blocks strategies that:

```text
require missing capabilities
try to write final_status.md
try to write certification.json
try to write policy_decision.json
try to forge verifier_artifacts/
claim DONE_PASS, PROVISIONAL_DONE, CERTIFIED_DONE, or final authority
```

This is deliberately conservative. A blocked strategy cannot be selected.

## Strategy Scoring

The scorer prefers strategies with:

```text
path to certifying verifier evidence
artifact-test support
expected final artifacts
lower risk
small capability surface
```

The score is a deterministic heuristic. It is not proof of plan quality.

## Selection Boundary

The selector writes:

```text
strategy_decision.json
selected_strategy.json
rejected_strategies.json
```

It does not write:

```text
final_status.md
certification.json
policy_decision.json
```

If the goal is unknown and no safe strategy is selected, the runner stops with `NEED_USER_STRATEGY` and does not fake DONE.

## What This Proves

v1.3 proves:

```text
deterministic task type routing works on fixture goals
capability inventory is recorded before strategy selection
strategy candidates are gated before scoring
forbidden status-writing strategies are rejected
certifiable strategies are ranked above weak strategies
selected strategy compiles into merged_plan.json
the worker executes the compiled plan
the certifier still writes the final status
```

## What This Does Not Prove

v1.3 does not prove:

```text
arbitrary task solving
live Mercury planning quality
full Pi goal-runner.chain.md autonomy
milestone planning
drift-aware replanning
trajectory-level evaluation
experience memory
domain pack quality
strategy search or MCTS
SWE-bench / OpenHands / mini-SWE-agent integration
```

Those are later roadmap items.

## Safe Claim

The safe claim is:

```text
The harness can deterministically route a prepared goal to a strategy, gate unsafe strategies, compile the selected strategy into a merged plan, execute it through the existing worker path, and rely on certify_run.py / policy_engine.py for final status.
```

The unsafe claim is:

```text
The planner can solve arbitrary goals autonomously.
```

Do not make the unsafe claim.
