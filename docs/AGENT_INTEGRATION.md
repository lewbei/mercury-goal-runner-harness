# Agent Integration Guide

## How any agent uses this harness

The harness is agent-agnostic. Any agent (Pi, Claude Code, Codex, Cursor, etc.)
can use it by following this protocol.

## Protocol

### Step 1: Initialize a run

```bash
python .agentic-pi/runtime/init_run.py --run-id <run_id>
```

This creates `.agentic-runs/<run_id>/` with `run_state.json`.

### Step 2: Write a goal contract

Create `.agentic-runs/<run_id>/goal_contract.json`:

```json
{
  "run_id": "<run_id>",
  "goal_type": "coding",
  "raw_user_prompt": "Create a README explaining the harness",
  "execution_prompt": "Create a README.md file that explains the Mercury Goal Runner Harness",
  "final_outputs": ["README.md"],
  "done_criteria": [
    "README.md exists",
    "README.md contains the word 'harness'"
  ],
  "constraints": ["Must use Python 3"]
}
```

### Step 3: Run the pipeline

```bash
python .agentic-pi/runtime/pi_cli.py goal-run <run_id>
```

This runs the full QRSPI pipeline:
1. INTAKE — compiles success criteria
2. RESEARCHING → DESIGNING → STRUCTURING → PLANNING — builds plan artifacts
3. IMPLEMENTING — executes steps via guarded worker
4. VALIDATOR_BUILDING — artifact routing, task graph
5. VALIDATING → EVIDENCE_INDEXING
6. POLICY_DECIDING → REPLAYING → CERTIFYING — verification + certification
7. REPORTING → MEMORY_CONSOLIDATING → DONE

### Step 4: Check status

```bash
python .agentic-pi/runtime/pi_cli.py goal-status <run_id>
```

Returns the certifier-owned status from `final_status.json`.

## What the agent produces

The agent's job is to write files into the run directory:

```
.agentic-runs/<run_id>/
├── goal_contract.json          (agent writes this)
├── step_logs/                  (agent writes these)
│   ├── 001.json
│   ├── 002.json
│   └── ...
├── <output files>              (agent writes these)
└── verifier_artifacts/         (agent writes these, optional)
    └── V.<AGENT>.json
```

### Step log format

Each step log must have:

```json
{
  "run_id": "<run_id>",
  "step_id": 1,
  "status": "PASSED",
  "action_taken": "create_file",
  "files_touched": ["README.md"],
  "commands_run": [],
  "evidence": ["Created README.md with harness explanation"],
  "pass_condition_satisfied": true,
  "remaining_work": []
}
```

### Verifier artifact format (optional, for P2 certification)

```json
{
  "artifact_id": "V.<AGENT>",
  "run_id": "<run_id>",
  "kind": "independent_test",
  "provenance_level": "P2",
  "authority": "certifying",
  "same_worker_as_solution": false,
  "executes_code": true,
  "assertion_count": 3,
  "verdict": "PASS"
}
```

## Agent-specific integration

### Pi

Pi uses the harness through QRSPI skills:

```
.pi/skills/question-contract/   → INTAKE phase
.pi/skills/research-pack/       → RESEARCHING phase
.pi/skills/design-options/      → DESIGNING phase
.pi/skills/structure-outline/   → STRUCTURING phase
.pi/skills/root-plan/           → PLANNING phase
```

Install: `pi install git:github.com/lewbei/mercury-goal-runner-harness`

### Claude Code

Claude Code can use the harness by:

1. Initialize: `python .agentic-pi/runtime/init_run.py --run-id my_goal`
2. Write `goal_contract.json`
3. Write step logs and output files
4. Run: `python .agentic-pi/runtime/pi_cli.py goal-run my_goal`
5. Check: `python .agentic-pi/runtime/pi_cli.py goal-status my_goal`

### Codex

Same protocol as Claude Code. The harness is agent-agnostic.

### Cursor

Same protocol. The harness doesn't care which agent writes the files.

## What the harness verifies

The certifier checks:

1. **Artifact location** — output files exist at expected paths
2. **Replay** — artifacts are reproducible
3. **Audit** — audit report is valid
4. **Drift** — no drift from expected behavior
5. **Formal verification** — contract annotations hold
6. **Evidence freeze** — evidence is immutable
7. **Memory authority** — memory doesn't claim certification authority
8. **Crypto signatures** — artifacts aren't tampered (if signed)

## What the harness does NOT do

- Does NOT write code (the agent does)
- Does NOT decide DONE (the certifier does)
- Does NOT trust the agent (it trusts evidence)
- Does NOT certify itself (the certifier is deterministic)

## Quick start (any agent)

```bash
# 1. Init
python .agentic-pi/runtime/init_run.py --run-id my_goal

# 2. Write goal contract (specify app name and output directory)
cat > .agentic-runs/my_goal/goal_contract.json << 'EOF'
{
  "run_id": "my_goal",
  "goal_type": "coding",
  "raw_user_prompt": "Build a todo app",
  "execution_prompt": "Build a todo app with React and TypeScript",
  "final_outputs": ["src/App.tsx", "package.json"],
  "done_criteria": ["App.tsx exists", "package.json exists"],
  "output_directory": "output/todo-app"
}
EOF

# 3. Run
python .agentic-pi/runtime/pi_cli.py goal-run my_goal

# 4. Check
python .agentic-pi/runtime/pi_cli.py goal-status my_goal

# 5. Product is at output/todo-app/
ls output/todo-app/
```

## Directory structure

The harness keeps infrastructure and product output separate:

```
my-project/
├── .agentic-pi/              ← harness (don't touch)
├── .agentic-runs/            ← run artifacts (don't touch)
│   └── <run_id>/
│       ├── goal_contract.json
│       ├── step_logs/
│       └── verifier_artifacts/
├── output/                   ← product output (clean)
│   └── <app-name>/           ← e.g. todo-app, weather-dashboard
│       ├── src/
│       ├── tests/
│       └── README.md
└── docs/                     ← harness docs
```

The agent writes product files to `output/<app-name>/`, not to the root.
The app name comes from the user's goal, not the run_id.
This keeps harness files and product files separate.
