# Scaling Architecture Plan (Updated)

## Goal

Scale the Mercury Goal Runner Harness to support multiple agents working in parallel, like Google Antigravity 2.0.

## Research Findings

### How Antigravity 2.0 actually works

```
ANTIGRAVITY STRUCTURE:
  /your-manager-base-path/
  ├── workspace-manager.py     ← CLI
  ├── .agent/
  │   └── skills/              ← Central skills library
  │       ├── public/          ← Official skills
  │       ├── private/         ← Your private skills
  │       └── user/            ← Local skills
  └── workspaces/              ← Each project is isolated
      ├── my-project/
      │   ├── .agent/
      │   │   └── skills       ← Symlink to central library
      │   └── skill-config.json ← Project-specific config
      └── another-project/
          ├── .agent/
          │   └── skills       ← Symlink to central library
          └── skill-config.json
```

### Key insight

**Workspace isolation = each project has its own `.agent/` directory with symlinked skills.**

This is different from my original plan:
- ❌ Not: each agent gets its own output directory
- ✅ Yes: each project gets its own `.agent/` directory with symlinked skills

## Proposed Architecture

```
mercury-goal-runner-harness/
├── .agentic-pi/                ← Central harness (shared)
├── workspaces/                 ← Each goal is isolated
│   ├── goal-001/
│   │   ├── .agentic-pi/       ← Symlink to central
│   │   ├── .agentic-runs/     ← Isolated runs
│   │   └── output/            ← Isolated output
│   └── goal-002/
│       ├── .agentic-pi/       ← Symlink to central
│       ├── .agentic-runs/     ← Isolated runs
│       └── output/            ← Isolated output
├── agent_manager.py           ← Orchestration dashboard
└── workspace_manager.py       ← Workspace management
```

## Workspace Configuration

Each workspace has a `workspace_config.json` that tells the agent what to do:

```json
{
  "goal": "Build a todo app",
  "skills": ["question-contract", "research-pack", "design-options"],
  "model": "claude-opus-4.7",
  "max_steps": 20,
  "output_dir": "output/todo-app"
}
```

### How it works

```
1. User: "Build a todo app"
2. workspace_manager.py creates workspace/
3. workspace_config.json is generated
4. .agentic-pi/ is symlinked
5. AGENTS.md is auto-generated with context
6. Agent runs in workspace/
7. Agent reads workspace_config.json to know what to do
```

### Context injection

Each workspace gets:

1. **workspace_config.json** — declares what workspace needs
2. **.agentic-pi/** — symlinked harness (shared)
3. **AGENTS.md** — auto-generated with context for the agent
4. **.agentic-runs/** — isolated runs
5. **output/** — isolated output

### Skills per workspace

Each workspace can have different skills:

```json
{
  "skills": [
    "question-contract",    ← for goal compilation
    "research-pack",        ← for research
    "design-options",       ← for design
    "structure-outline",    ← for structure
    "root-plan"             ← for planning
  ]
}
```

The agent reads `workspace_config.json` to know which skills to use.

## Implementation Plan

### Phase 1: Workspace Isolation (1 week)

1. Create `workspace_manager.py`
   - Create workspaces: `workspace_manager.py create <goal-name>`
   - List workspaces: `workspace_manager.py list`
   - Delete workspaces: `workspace_manager.py delete <goal-name>`

2. Create workspace structure
   - Each workspace gets its own `.agentic-pi/` symlink
   - Each workspace gets its own `.agentic-runs/` directory
   - Each workspace gets its own `output/` directory

3. Update `run_goal.py` to use workspace
   - Run in workspace directory
   - Use workspace-specific paths

### Phase 2: Parallel Execution (2 weeks)

1. Create `parallel_runner.py`
   - Execute multiple workspaces simultaneously
   - Manage workspace lifecycle
   - Handle errors and retries

2. Create `token_tracker.py`
   - Track token usage per workspace
   - Aggregate usage across workspaces
   - Report usage statistics

### Phase 3: Agent Manager (2 weeks)

1. Create `agent_manager.py`
   - Dashboard to orchestrate multiple workspaces
   - Start/stop/pause workspaces
   - Monitor workspace status
   - View workspace output

2. Create CLI commands
   - `mercury agents list` — list running workspaces
   - `mercury agents start <goal>` — start new workspace
   - `mercury agents stop <workspace>` — stop workspace
   - `mercury agents status <workspace>` — check workspace status

### Phase 4: Integration (1 week)

1. Update `run_goal.py` to support workspaces
2. Update `certify_run.py` to handle workspaces
3. Update tests
4. Update documentation

## Success Criteria

1. Multiple workspaces can run in parallel
2. Each workspace has isolated output
3. Agent manager can orchestrate multiple workspaces
4. Token usage is tracked
5. Existing tests still pass

## Risks

1. **Symlink complexity**: Symlinks may not work on all platforms
   - Mitigation: Use copies instead of symlinks on Windows

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
