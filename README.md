# Mercury Goal Runner Harness

A goal execution harness for AI coding agents. The agent says what it wants to build. The harness handles planning, execution, verification, and certification.

## What it does

```
Agent says: "Build a todo app"
    ↓
Harness does:
    1. Compile goal → goal_contract.json
    2. Plan steps → step_logs/
    3. Execute → output/todo-app/
    4. Verify → certifier gates
    5. Certify → final_status.json
    ↓
Agent sees: CERTIFIED_DONE or FAILED
```

## Quick start

```bash
# Clone
git clone https://github.com/lewbei/mercury-goal-runner-harness
cd mercury-goal-runner-harness

# Run a goal
python mercury.py run "Create a hello world script"

# Check status
python mercury.py status <run_id>

# Health check
python mercury.py health
```

## How it works

The harness follows the QRSPI pipeline:

```
INTAKE → RESEARCHING → DESIGNING → STRUCTURING → PLANNING
    ↓
IMPLEMENTING → VALIDATOR_BUILDING → VALIDATING
    ↓
EVIDENCE_INDEXING → POLICY_DECIDING → REPLAYING → CERTIFYING
    ↓
REPORTING → MEMORY_CONSOLIDATING → DONE
```

Each phase produces artifacts. The certifier verifies all artifacts before certifying DONE.

## Directory structure

```
mercury-goal-runner-harness/
├── mercury.py              ← simple CLI (start here)
├── AGENTS.md               ← agent instructions (Codex, generic)
├── CLAUDE.md               ← Claude Code instructions
├── .cursorrules            ← Cursor instructions
├── .windsurfrules          ← Windsurf instructions
├── .agentic-pi/            ← harness internals (don't edit)
├── .agentic-runs/          ← run artifacts (don't edit)
├── output/                 ← product output (clean)
│   └── <app-name>/         ← e.g. todo-app, weather-dashboard
├── tests/                  ← harness tests
└── docs/                   ← documentation
```

## For agents

Any agent can use the harness:

```bash
# One command
python mercury.py run "what the user wants to build"
```

The agent doesn't need to know file formats, protocols, or harness internals. Just describe the goal.

See [docs/AGENT_GUIDE.md](docs/AGENT_GUIDE.md) for details.

## For developers

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the harness works internally.

## Rules

1. Product files go to `output/<app-name>/`
2. Don't edit `.agentic-pi/` or `.agentic-runs/`
3. Don't claim DONE — the certifier decides
4. Trust evidence, not vibes

## Status

Check harness health:

```bash
python mercury.py health
```

Expected output:
```
HEALTHY - no gaps detected
```

## License

MIT
