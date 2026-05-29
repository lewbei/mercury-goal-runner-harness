# Agent Guide

How any AI agent uses the Mercury Goal Runner Harness.

## One command

```bash
python mercury.py run "what the user wants to build"
```

That's it. The agent doesn't need to know anything else.

## What happens

```
Agent: python mercury.py run "Build a todo app"
    ↓
Harness:
    1. Creates run directory (.agentic-runs/<run_id>/)
    2. Writes goal_contract.json
    3. Runs QRSPI pipeline
    4. Writes product to output/todo-app/
    5. Certifier writes final_status.json
    ↓
Agent: python mercury.py status <run_id>
    ↓
Output: CERTIFIED_DONE or FAILED
```

## Commands

```bash
# Run a goal
python mercury.py run "Build a todo app"

# Run with custom output directory
python mercury.py run "Build a todo app" --output my-todo-app

# Run with custom run ID
python mercury.py run "Build a todo app" --run-id my_goal

# Check status
python mercury.py status <run_id>

# Health check
python mercury.py health
```

## Output location

Product files go to `output/<app-name>/`:

```
output/
├── todo-app/           ← built a todo app
├── weather-dashboard/  ← built a weather dashboard
└── api-server/         ← built an API server
```

The app name comes from the goal, not the run ID.

## Rules

1. **Product files** go to `output/<app-name>/`
2. **Don't edit** `.agentic-pi/` or `.agentic-runs/`
3. **Don't claim DONE** — the certifier decides
4. **Trust evidence** — check `final_status.json`, not vibes

## Status interpretation

```bash
python mercury.py status <run_id>
```

Output:
```
Run:     run_20260529_abc123
Status:  CERTIFIED_DONE
Checks:  8/8
Source:  .agentic-runs/run_20260529_abc123/final_status.json
```

Status values:
- `CERTIFIED_DONE` — all gates passed, product is verified
- `FAILED` — one or gates failed, check logs
- `NOT_CERTIFIED` — run not complete yet

## Agent-specific setup

### Pi

Already integrated. Use QRSPI skills or `mercury.py`.

### Claude Code

Reads `CLAUDE.md` automatically. Just run `python mercury.py run "goal"`.

### Cursor

Reads `.cursorrules` automatically. Just run `python mercury.py run "goal"`.

### Windsurf

Reads `.windsurfrules` automatically. Just run `python mercury.py run "goal"`.

### Codex

Reads `AGENTS.md` automatically. Just run `python mercury.py run "goal"`.

### Any other agent

```bash
python mercury.py run "what the user wants to build"
```

## Troubleshooting

### Run not found

```bash
python mercury.py status <run_id>
# Run not found: <run_id>
```

Check the run ID. List runs:
```bash
ls .agentic-runs/
```

### Health check fails

```bash
python mercury.py health
# UNHEALTHY - gaps detected
```

Check the output for details. Usually a missing test or dead code.

### Product not created

```bash
python mercury.py status <run_id>
# Status: FAILED
```

Check step logs:
```bash
cat .agentic-runs/<run_id>/step_logs/001.json
```
