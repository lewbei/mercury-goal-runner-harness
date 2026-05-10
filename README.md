# Mercury Goal Runner Harness

QRSPI-phased goal execution harness for Pi coding agent. Planner designs, worker codes, verifier proves, certifier decides. Every step produces evidence. Final status comes only from deterministic checks.

## Core Question

```text
Who is allowed to certify DONE?
Pi orchestrates. Agents plan, code, verify.
Policy decides. Certifier writes final status.
Pi only reports what the certifier wrote.
```

## Install

```bash
pi install git:github.com/lewbei/mercury-goal-runner
```

Or locally:
```bash
pi install .
```

## Quick Start

```bash
# 1. Init a run
python .agentic-pi/runtime/init_run.py --run-id my_goal

# 2. Create goal contract at .agentic-runs/my_goal/goal_contract.json
# 3. Spawn planner-minimal agent → thinking_plan.md + plan_graph.json + merged_plan.json
# 4. Spawn guarded-worker agent → code + step_logs + trace
# 5. Spawn verifier-generator agent → verifier_contract + P2 evidence
# 6. Run deterministic pipeline
python .agentic-pi/runtime/orchestrate_pipeline.py --run-id my_goal

# 7. Check result
python .agentic-pi/runtime/check_matrix.py .agentic-runs/my_goal --all
```

## Architecture

```
QRSPI Phases:
  Q: Question  → question-contract skill → understand goal
  R: Research  → research-pack skill → explore approaches
  S: Structure → design-options + structure-outline → plan_graph.json
  P: Plan      → root-plan → thinking_plan.md + merged_plan.json
  I: Implement → guarded-worker → code + step_logs + trace

Gates:
  PlanGraph          → validates node/edge structure
  Step Logs          → validates evidence format
  Code Execution     → runs output, checks 2+ lines
  Formal Verification → #@ Requires/Ensures contract compliance
  Cryptographic      → Ed25519 artifact signing, tamper detection
  Verifier Evidence  → P2 independent attestation
  Policy Engine      → decides between PROVISIONAL/CERTIFIED/NOT_DONE

Memory:
  Project-local (.agentic-pi/memory/durable/)
  Worker reads memory before coding
  Repair agent queries memory for similar failures
  Learning loop: fail → fix → store → next run benefits
```

## Agents

| Agent | Model | Role |
|-------|-------|------|
| `planner-minimal` | merc-2 | Q→R→S→P design with code templates |
| `planner-robust` | merc-2 | Thorough plan with validation strategy |
| `guarded-worker` | ds-flash | Codes from template, writes step logs |
| `verifier-generator` | ds-flash | Independent P2 verifier evidence |
| `skeptic-planner` | merc-2 | Finds failure modes, critiques plans |
| `plan-selector` | ds-flash | Picks best plan from debate |
| `verifier-reviewer` | ds-flash | Reviews verifier evidence quality |

## Python Backend

```
.agentic-pi/
├── validators/
│   ├── certify_run.py          Deterministic certifier
│   ├── validate_schema.py      JSON schema validator
│   └── validate_plan_graph.py  Plan graph structure
├── runtime/
│   ├── orchestrate_pipeline.py 6-phase deterministic runner
│   ├── check_matrix.py         Horizontal check matrix (each independent)
│   ├── adversarial_loop.py     Skeptic → find breaks → repair → re-certify
│   ├── build_repair_prompt.py  Memory-aware repair prompt builder
│   ├── run_subagent_memory.py  Capture learnings per subagent
│   └── project_adapter.py      Map project structure for harness
├── formal/
│   ├── harness_contract_verifier.py  #@ Requires/Ensures runtime check
│   └── harness_signing.py           Ed25519 signing + verification
└── memory/
    └── durable/                 Project-local learning store
```

## Checks

Each check independent, re-runnable individually:

```bash
python .agentic-pi/runtime/check_matrix.py <run_dir> --all

  [plan_graph]        PASS
  [step_logs]         PASS
  [code_execution]    PASS
  [formal_verification] PASS
  [crypto_signatures] SKIP
```

Re-run just one:
```bash
python .agentic-pi/runtime/check_matrix.py <run_dir> code_execution
```

## Design Principles

```text
Vertical first, horizontal later.
Prove one slice end-to-end before expanding.
One failure mode → one fixture → one implementation → one validator → one test.
Agents do the work. Pi orchestrates. No manual edits to fix agent output.
Memory feeds the worker/repair, not the planner.
```

## Docs

- `AGENTS.md` — Agent instructions and rules
- `docs/FRAMEWORK.md` — Conceptual architecture and file map
- `docs/PROJECT_STATUS.md` — Version history and proof summary
- `docs/` — All version documentation (V0.1–V5)
