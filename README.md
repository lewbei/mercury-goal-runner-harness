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

## Install

### Pi

```bash
pi install git:github.com/lewbei/mercury-goal-runner-harness
```

### Claude Code

Clone the repo. Claude Code reads `CLAUDE.md` automatically.

### Cursor

Clone the repo. Cursor reads `.cursorrules` automatically.

### Windsurf

Clone the repo. Windsurf reads `.windsurfrules` automatically.

### Codex

Clone the repo. Codex reads `AGENTS.md` automatically.

### Any other agent

```bash
git clone https://github.com/lewbei/mercury-goal-runner-harness
cd mercury-goal-runner-harness
```

## Quick start

```bash
# Run a goal
python mercury.py run "Create a hello world script"

# Check status
python mercury.py status <run_id>

# Health check
python mercury.py health
```

## Examples

```bash
# Build a web app
python mercury.py run "Build a todo app with React"

# Build an API
python mercury.py run "Create a REST API for user management"

# Build a CLI tool
python mercury.py run "Create a CLI tool that converts CSV to JSON"

# Build a library
python mercury.py run "Create a Python library for date parsing"
```

Product goes to `output/<app-name>/`:

```
output/
├── todo-app/
├── user-api/
├── csv-to-json/
└── date-parser/
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

## Verification

The certifier runs 8 gates:

```
Layer 1 (basic):
  - artifact_location: output files exist
  - replay: artifacts are reproducible
  - audit: audit report is valid

Layer 2 (intermediate):
  - drift_report: no drift from expected behavior
  - formal_verification: contract annotations hold

Layer 3 (high rigor):
  - evidence_freeze: evidence is immutable
  - memory_authority: memory doesn't claim certification
  - crypto_signature: artifacts aren't tampered
```

All 8 gates must pass for CERTIFIED_DONE.

## Directory structure

```
mercury-goal-runner-harness/
├── mercury.py              ← simple CLI (start here)
├── README.md               ← main docs
├── AGENTS.md               ← agent instructions (Codex, generic)
├── CLAUDE.md               ← Claude Code instructions
├── .cursorrules            ← Cursor instructions
├── .windsurfrules          ← Windsurf instructions
├── package.json            ← Pi package config
├── extensions/             ← Pi extension (TypeScript)
├── .pi/                    ← Pi skills (for Pi agent)
├── .agentic-pi/            ← harness internals (don't edit)
├── .agentic-runs/          ← run artifacts (gitignored)
├── output/                 ← product output (gitignored)
├── modules/                ← reference material (gitignored)
├── tests/                  ← harness tests
└── docs/                   ← documentation
```

## Rules

1. Product files go to `output/<app-name>/`
2. Don't edit `.agentic-pi/` or `.agentic-runs/`
3. Don't claim DONE — the certifier decides
4. Trust evidence, not vibes

## Health check

```bash
python mercury.py health
```

Expected output:
```
HEALTHY - no gaps detected
```

Checks:
- Module coverage: 229/229
- Critical path gaps: 0
- Dead code: 0
- Gate coverage: 10/10

## FAQ

**Q: What agents does it work with?**
A: Pi, Claude Code, Cursor, Windsurf, Codex, and any agent that can run shell commands.

**Q: Do I need to know the file formats?**
A: No. Just run `python mercury.py run "goal"`.

**Q: Where does the product go?**
A: `output/<app-name>/`. The app name comes from the goal.

**Q: What if the run fails?**
A: Check `python mercury.py status <run_id>` for details. Check step logs in `.agentic-runs/<run_id>/step_logs/`.

**Q: Can I edit the harness?**
A: You can edit `mercury.py` and docs. Don't edit `.agentic-pi/` or `.agentic-runs/`.

**Q: How do I know it's working?**
A: Run `python mercury.py health`. It should say `HEALTHY - no gaps detected`.

## License

MIT
