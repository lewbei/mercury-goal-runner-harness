# Architecture

How the Mercury Goal Runner Harness works internally.

## Core principle

```
Who certifies DONE?
The agent plans, codes, verifies.
The policy decides.
The certifier writes final status.
The agent only reports what the certifier wrote.
```

The agent cannot certify itself. Only the deterministic certifier can write `final_status.json`.

## Pipeline phases

```
INTAKE
  └─ Compiles goal_contract.json from raw user prompt

RESEARCHING → DESIGNING → STRUCTURING → PLANNING
  └─ Builds plan artifacts (research_pack, design_options, root_plan, step_plan)

IMPLEMENTING
  └─ Guarded worker executes steps, writes step_logs/

VALIDATOR_BUILDING
  └─ Builds artifact_routing, task_graph, capability_inventory

VALIDATING → EVIDENCE_INDEXING
  └─ Runs verifiers, indexes evidence

POLICY_DECIDING
  └─ Policy engine evaluates evidence, decides pass/fail

REPLAYING
  └─ Replays run for determinism check

CERTIFYING
  └─ Certifier runs 8 gates, writes final_status.json

REPORTING → MEMORY_CONSOLIDATING → DONE
  └─ Generates report, consolidates learnings
```

## Certifier gates (verification pyramid)

The certifier runs 8 gates in order of speed/rigor:

```
Layer 1 (basic, ~5ms):
  - artifact_location: output files exist
  - replay: artifacts are reproducible
  - audit: audit report is valid

Layer 2 (intermediate, ~10ms):
  - drift_report: no drift from expected behavior
  - formal_verification: contract annotations hold

Layer 3 (high rigor, ~350ms):
  - evidence_freeze: evidence is immutable
  - memory_authority: memory doesn't claim certification
  - crypto_signature: artifacts aren't tampered
```

## Authority model

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

## Key files

```
.agentic-pi/
├── runtime/
│   ├── run_goal.py          ← QRSPI pipeline orchestrator
│   ├── guarded_worker       ← step execution with write-scope guard
│   ├── policy_engine.py     ← artifact routing + policy decisions
│   ├── certify_run.py       ← certifier (writes final_status.json)
│   ├── full_verify.py       ← mandatory skeptic review
│   └── harness_health.py    ← health check
├── validators/
│   ├── certifier_gates.py   ← 8 certifier gates
│   └── verify_agent_outputs.py
├── formal/
│   ├── harness_contract_verifier.py  ← AST-only contract verification
│   └── harness_signing.py            ← Ed25519 artifact signing
└── memory/
    └── durable/             ← cross-run learnings
```

## What the agent produces

```
.agentic-runs/<run_id>/
├── goal_contract.json          ← what to do
├── run_state.json              ← current phase
├── step_logs/                  ← what was done
│   ├── 001.json
│   ├── 002.json
│   └── ...
├── verifier_artifacts/         ← optional P2 evidence
│   └── V.<AGENT>.json
└── final_status.json           ← certifier-owned (don't edit)
```

## What the harness produces

```
output/<app-name>/              ← product files
├── src/
├── tests/
└── README.md
```

## Health check

```bash
python mercury.py health
```

Checks:
- Module coverage (229/229)
- Critical path gaps (0)
- Dead code (0)
- Gate coverage (10/10)
- Doc freshness (0 issues)

Expected: `HEALTHY - no gaps detected`
