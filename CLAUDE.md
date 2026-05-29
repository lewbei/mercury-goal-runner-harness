# Mercury Goal Runner Harness

This project uses the Mercury Goal Runner Harness for goal execution and verification.

## How to use

When the user asks you to build something, use the harness:

```bash
python .agentic-pi/runtime/run_goal.py --run-id <run_id> --command "what the user wants to build"
```

The harness handles:
1. Goal compilation
2. Planning (QRSPI phases)
3. Execution (guarded worker)
4. Verification (certifier gates)
5. Certification (deterministic status)

## Output

Product files go to `output/<app-name>/`. Harness files stay in `.agentic-pi/`.

## Status

Check status with:
```bash
python .agentic-pi/runtime/pi_cli.py goal-status <run_id>
```

## Health check

```bash
python .agentic-pi/runtime/harness_health.py
```

## Rules

1. Do NOT edit files in `.agentic-pi/` or `.agentic-runs/`
2. Do NOT claim DONE — only the certifier can certify
3. Write product files to `output/<app-name>/`
4. Trust evidence, not vibes
