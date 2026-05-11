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

This is a prepared-run harness. The runtime is strict: it does not create missing planner or verifier proof artifacts for you.

```bash
# 1. Init a run
python .agentic-pi/runtime/init_run.py --run-id my_goal

# 2. Create goal_contract.json and expected_artifacts.json under .agentic-runs/my_goal/
#    If prompt-compiler creates goal_contract.json, also record prompt provenance:
python .agentic-pi/runtime/prompt_provenance.py .agentic-runs/my_goal
python .agentic-pi/validators/validate_prompt_provenance.py .agentic-runs/my_goal

# 3. Create planner-owned plan JSON at .agentic-runs/my_goal/plans/<planner>_plan.json
# 4. Select and merge the plan
python .agentic-pi/runtime/plan_selector.py --run-id my_goal
python .agentic-pi/runtime/plan_merger.py --run-id my_goal
python .agentic-pi/runtime/plan_graph_builder.py my_goal

# 5. Execute approved create_file steps and write evidence
python .agentic-pi/runtime/guarded_worker.py --run-id my_goal

# 6. Add verifier_contract.json and verifier_artifacts/*.json
# 7. Run the strict proof-artifact verifier and certifier path
python .agentic-pi/runtime/full_verify.py .agentic-runs/my_goal

# 8. Read certifier-owned final_status.json; do not self-certify DONE
```

## Architecture

```
QRSPI Phases:
  Q: Question  → question-contract skill → understand goal
  R: Research  → research-pack skill → explore approaches
  S: Structure → design-options + structure-outline → planner-owned plan JSON
  P: Plan      → selected_plan.json + merged_plan.json + plan_graph.json
  I: Implement → guarded-worker → code + step_logs + trace

Gates:
  PlanGraph          → validates node/edge structure
  Step Logs          → validates evidence format
  Code Execution     → runs output, checks 2+ lines
  Formal Verification → #@ Requires/Ensures contract compliance
  Cryptographic      → Ed25519 artifact signing, tamper detection
  Verifier Evidence  → P2 independent attestation
  Policy Engine      → decides between PROVISIONAL/CERTIFIED/NOT_DONE

Prompt provenance:
  .agentic-runs/<run_id>/prompt_provenance/prompt_compiler.prompt.json
  Records raw_user_prompt -> execution_prompt hashes and prompt-compiler file hashes
  Provenance only; cannot certify DONE or replace verifier evidence

Memory:
  Project-local (.agentic-pi/memory/durable/)
  Advisory only; memory cannot certify DONE
  Worker may read memory before coding
  Run-local and quarantine memory are validated under .agentic-runs/<run_id>/memory/
  Durable memory promotion goes through memory_write_gate.py after certifier lock
  Learning records stay outside final-status authority
```

## Agents

| Agent | Model | Role |
|-------|-------|------|
| `prompt-compiler` | mercury-2 | Converts raw prompt into measurable goal contract + execution prompt |
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
│   ├── certify_run.py                 Deterministic certifier
│   ├── validate_schema.py             JSON schema validator
│   ├── validate_plan_graph.py         Plan graph structure
│   ├── validate_prompt_eval_case.py   Prompt compiler seed eval fixtures
│   └── validate_prompt_provenance.py  Prompt provenance authority boundary
├── runtime/
│   ├── full_verify.py                 Recommended strict proof-artifact verifier; no synthesized proof files
│   ├── prompt_provenance.py           Records raw prompt -> execution_prompt provenance
│   ├── run_prompt_compiler_eval.py    Scores prompt-compiler seed eval cases
│   ├── orchestrate_pipeline.py        Lower-level deterministic phase runner; fails on phase failure
│   ├── plan_router.py          Requires existing plans/*_plan.json
│   ├── plan_merger.py          Writes merged_plan.json from selected_plan.json
│   ├── check_matrix.py         Horizontal check matrix (each independent)
│   ├── adversarial_loop.py     Diagnostic repair loop tool; not certification authority
│   ├── build_repair_prompt.py  Memory-aware repair prompt builder
│   ├── run_subagent_memory.py  Capture advisory learnings per subagent
│   └── project_adapter.py      Map project structure for harness
├── formal/
│   ├── harness_contract_verifier.py  #@ Requires/Ensures runtime check
│   └── harness_signing.py           Ed25519 signing + verification
└── memory/
    └── durable/                 Project-local learning store
```

## Checks

Use checks as evidence, not as self-certification. Final status still comes from certifier-owned artifacts.

```bash
python .agentic-pi/runtime/check_matrix.py <run_dir> --all
python .agentic-pi/runtime/full_verify.py <run_dir>
python .agentic-pi/validators/certify_run.py <run_dir>
```

## Design Principles

```text
Vertical first, horizontal later.
Prove one slice end-to-end before expanding.
One failure mode → one fixture → one implementation → one validator → one test.
Agents do the work. Pi orchestrates. No manual edits to final status artifacts.
Memory can advise worker/repair, but cannot certify DONE.
```

## Docs

- `AGENTS.md` — Agent instructions and rules
- `docs/CURRENT_RUNTIME_PATH.md` — current strict runtime boundary and compatibility map
- `docs/PLAN_ROUTER.md` — current plan-router boundary; no generated substitute planning
- `docs/FRAMEWORK.md` — conceptual architecture and file map
- `docs/PROJECT_STATUS.md` — version history, local status, and proof-slice limits
- `docs/workspace_index.md` — source-of-truth file map and cleanup debt
- `docs/` — versioned historical records plus current architecture docs; old V0/V1 docs are not the default runtime contract
