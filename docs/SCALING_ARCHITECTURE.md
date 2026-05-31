# Scaling Architecture Plan

## Goal

Scale the Mercury Goal Runner Harness to support multiple agents working in parallel, like Google Antigravity 2.0.

## Research Findings

### How Antigravity 2.0 works

- **Agent Manager**: Dashboard to orchestrate multiple agents
- **Workspace Isolation**: Each agent gets its own workspace (directory)
- **Parallel Execution**: Multiple agents work simultaneously
- **Token Management**: Track usage across agents

### Key insight

Antigravity runs agents in **separate workspaces** (isolated directories). No shared state between agents.

## Current Harness Architecture

```
mercury-goal-runner-harness/
├── .agentic-runs/
│   ├── run_001/          ← isolated run
│   ├── run_002/          ← isolated run
│   └── run_003/          ← isolated run
└── output/
    └── todo-app/         ← shared output (problem!)
```

**Problem:** Output goes to `output/<app-name>/`, which is shared. If two agents build a "todo-app", they conflict.

## Proposed Architecture

```
mercury-goal-runner-harness/
├── .agentic-runs/
│   ├── run_001/
│   ├── run_002/
│   └── run_003/
├── output/
│   ├── run_001/          ← isolated output
│   ├── run_002/          ← isolated output
│   └── run_003/          ← isolated output
└── .agentic-pi/
    └── runtime/
        ├── agent_manager.py      ← orchestration dashboard
        ├── parallel_runner.py    ← parallel execution
        └── token_tracker.py      ← token usage tracking
```

## Implementation Plan

### Phase 1: Isolated Output (1 week)

1. Change output path: `output/<run_id>/` instead of `output/<app-name>/`
2. Update `guarded_worker.py` to write to `output/<run_id>/`
3. Update `mercury.py` to use `output/<run_id>/`
4. Update documentation

### Phase 2: Parallel Execution (2 weeks)

1. Create `parallel_runner.py`
   - Execute multiple runs simultaneously
   - Manage run lifecycle
   - Handle errors and retries

2. Create `token_tracker.py`
   - Track token usage per run
   - Aggregate usage across runs
   - Report usage statistics

### Phase 3: Agent Manager (2 weeks)

1. Create `agent_manager.py`
   - Dashboard to orchestrate multiple agents
   - Start/stop/pause agents
   - Monitor agent status
   - View agent output

2. Create CLI commands
   - `mercury agents list` — list running agents
   - `mercury agents start <goal>` — start new agent
   - `mercury agents stop <run_id>` — stop agent
   - `mercury agents status <run_id>` — check agent status

### Phase 4: Integration (1 week)

1. Update `run_goal.py` to support parallel execution
2. Update `certify_run.py` to handle multiple runs
3. Update tests
4. Update documentation

## Success Criteria

1. Multiple agents can run in parallel
2. Each agent has isolated output
3. Agent manager can orchestrate multiple runs
4. Token usage is tracked
5. Existing tests still pass

## Risks

1. **File conflicts**: Agents may conflict on shared files
   - Mitigation: Isolated output directories

2. **Token usage**: May exceed limits
   - Mitigation: Token tracking and limits

3. **Complexity**: More complex to manage
   - Mitigation: Agent manager dashboard

## Timeline

- Phase 1: 1 week
- Phase 2: 2 weeks
- Phase 3: 2 weeks
- Phase 4: 1 week

**Total: 6 weeks**
