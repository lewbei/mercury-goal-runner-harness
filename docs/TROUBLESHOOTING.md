# Troubleshooting Guide

## Common Issues

### 1. Run not found

**Error:** `Run 'run_id' has no run_state.json`

**Solution:** Initialize the run first:
```bash
python .agentic-pi/runtime/init_run.py --run-id <run_id>
```

### 2. Goal contract invalid

**Error:** `goal_contract.json schema invalid`

**Solution:** Check the goal contract schema in `.agentic-pi/schemas/goal_contract.schema.json`

### 3. Verification fails

**Error:** `verification checkpoint failed`

**Solution:** Check the verification feedback in `.agentic-runs/<run_id>/verification_feedback.json`

### 4. Certification fails

**Error:** `certification failed`

**Solution:** Check the certification report in `.agentic-runs/<run_id>/certification.json`

### 5. Health check fails

**Error:** `UNHEALTHY - gaps detected`

**Solution:** Run the health check to see details:
```bash
python .agentic-pi/runtime/harness_health.py
```

## Agent-Specific Issues

### Pi

**Issue:** QRSPI skills not loading

**Solution:** Check `.pi/settings.json` and ensure the harness is installed.

### Claude Code

**Issue:** CLAUDE.md not read

**Solution:** Ensure CLAUDE.md is at the repo root.

### Cursor

**Issue:** .cursorrules not read

**Solution:** Ensure .cursorrules is at the repo root.

### Codex

**Issue:** AGENTS.md not read

**Solution:** Ensure AGENTS.md is at the repo root.

## Performance Issues

### 1. Slow execution

**Cause:** Large goals with many steps

**Solution:** Break down the goal into smaller steps.

### 2. Memory issues

**Cause:** Large context window

**Solution:** Use the context manager to monitor usage.

### 3. Timeout issues

**Cause:** Long-running tasks

**Solution:** Use the long-horizon manager for checkpoints.

## Debugging

### 1. Check run state

```bash
cat .agentic-runs/<run_id>/run_state.json
```

### 2. Check step logs

```bash
ls -la .agentic-runs/<run_id>/step_logs/
```

### 3. Check verification feedback

```bash
cat .agentic-runs/<run_id>/verification_feedback.json
```

### 4. Check certification

```bash
cat .agentic-runs/<run_id>/certification.json
```

### 5. Check health

```bash
python .agentic-pi/runtime/harness_health.py
```

## Getting Help

1. Check the documentation in `docs/`
2. Run the health check
3. Check the known issues in `docs/KNOWN_ISSUES.md`
4. Open an issue on GitHub
