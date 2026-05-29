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

## How agents use it

Each agent uses the harness through its own mechanism:

### Pi

Pi uses QRSPI skills automatically. Just describe the goal.

### Claude Code

Reads `CLAUDE.md` and uses the harness directly.

### Cursor

Reads `.cursorrules` and uses the harness directly.

### Codex

Reads `AGENTS.md` and uses the harness directly.

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

The harness has multi-level verification:

```
Planning level:
  - verification_checkpoint.py runs verifier during planning
  - replanning_loop.py adjusts plan based on feedback

Step level:
  - step_verifier.py verifies each step after execution
  - Checks file exists, Python syntax, JSON validity

Final level:
  - certifier gates verify all artifacts
  - 8 gates: artifact_location, replay, audit, drift_report,
    formal_verification, evidence_freeze, memory_authority, crypto_signature
```

## Directory structure

```
mercury-goal-runner-harness/
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

## Model Configuration

The harness supports configurable models. See [docs/MODEL_CONFIGURATION.md](docs/MODEL_CONFIGURATION.md) for details.

### Quick Setup

```bash
# Set model via environment variable
export MERCURY_MODEL=inception/mercury-2

# Or create .agentic-pi/config.json
{
  "model": "inception/mercury-2",
  "thinking": "xhigh"
}
```

### Supported Models

- `inception/mercury-2` — Mercury (fast, good for coding)
- `deepseek/deepseek-v4-flash` — DeepSeek Flash (fast, cheap)
- `anthropic/claude-sonnet-4` — Claude Sonnet (complex tasks)
- `openai/gpt-4o` — GPT-4o (general tasks)
- `ollama/codellama` — CodeLlama (local, no API key)

### API Keys

Cloud models require API keys. Local models (Ollama) don't.

See [docs/MODEL_CONFIGURATION.md](docs/MODEL_CONFIGURATION.md) for API key setup.

## Rules

1. Product files go to `output/<app-name>/`
2. Don't edit `.agentic-pi/` or `.agentic-runs/`
3. Don't claim DONE — the certifier decides
4. Trust evidence, not vibes

## Health check

```bash
python .agentic-pi/runtime/harness_health.py
```

Expected output:
```
HEALTHY - no gaps detected
```

## FAQ

**Q: What agents does it work with?**
A: Pi, Claude Code, Cursor, Windsurf, Codex, and any agent that can run shell commands.

**Q: Do I need a CLI?**
A: No. Each agent uses the harness through its own mechanism (skills, CLAUDE.md, .cursorrules, AGENTS.md).

**Q: Where does the product go?**
A: `output/<app-name>/`. The app name comes from the goal.

**Q: What if the run fails?**
A: Check the step logs in `.agentic-runs/<run_id>/step_logs/`.

**Q: Can I edit the harness?**
A: You can edit docs. Don't edit `.agentic-pi/` or `.agentic-runs/`.

**Q: How do I know it's working?**
A: Run `python .agentic-pi/runtime/harness_health.py`. It should say `HEALTHY - no gaps detected`.

## License

MIT
