# Workspace Index

## Root Directory

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

## Documentation

### Main Docs

- `README.md` - main documentation
- `AGENTS.md` - agent instructions
- `CLAUDE.md` - Claude Code instructions
- `.cursorrules` - Cursor instructions
- `.windsurfrules` - Windsurf instructions

### Technical Docs

- `docs/ARCHITECTURE.md` - internal design
- `docs/FRAMEWORK.md` - framework overview
- `docs/AGENT_GUIDE.md` - agent guide
- `docs/MODEL_CONFIGURATION.md` - model setup
- `docs/PROJECT_STATUS.md` - project status

### Analysis Docs

- `docs/PLANNING_GAP_ANALYSIS.md` - planning analysis
- `docs/NEXT_PHASE_PLAN.md` - next phase plan
- `docs/KNOWN_ISSUES.md` - known issues
- `docs/TROUBLESHOOTING.md` - troubleshooting guide
- `docs/AGENT_TESTING_RESULTS.md` - testing results

### Social Media Docs

- `docs/LINKEDIN_POST.md` - LinkedIn post
- `docs/REDDIT_POST.md` - Reddit post
- `docs/TWITTER_POST.md` - Twitter post

## Harness Internals

### Runtime

- `.agentic-pi/runtime/run_goal.py` - main pipeline
- `.agentic-pi/runtime/guarded_worker.py` - step execution
- `.agentic-pi/runtime/verification_checkpoint.py` - planning verification
- `.agentic-pi/runtime/step_verifier.py` - step verification
- `.agentic-pi/runtime/replanning_loop.py` - replanning
- `.agentic-pi/runtime/context_manager.py` - context management
- `.agentic-pi/runtime/long_horizon_manager.py` - long-horizon support
- `.agentic-pi/runtime/parallel_executor.py` - parallel execution
- `.agentic-pi/runtime/research_module.py` - research module
- `.agentic-pi/runtime/resume_module.py` - resume mechanism
- `.agentic-pi/runtime/cross_run_learner.py` - cross-run learning

### Validators

- `.agentic-pi/validators/certifier_gates.py` - certifier gates
- `.agentic-pi/validators/certify_run.py` - certification
- `.agentic-pi/validators/verify_agent_outputs.py` - verification

### Formal Verification

- `.agentic-pi/formal/harness_contract_verifier.py` - contract verification
- `.agentic-pi/formal/harness_signing.py` - cryptographic signing

## Tests

- `tests/test_verification_replanning.py` - verification tests
- `tests/test_step_verifier.py` - step verifier tests
- `tests/test_context_manager.py` - context manager tests
- `tests/test_long_horizon_manager.py` - long-horizon tests
- `tests/test_parallel_executor.py` - parallel executor tests
- `tests/test_research_resume.py` - research and resume tests
- `tests/test_certifier_gates.py` - certifier gate tests
- `tests/test_certifier_modularization_pre_audit.py` - modularization tests

## Related Documents

- [V3.5 to V4.0 Authority Evidence Memory Plan](V3_5_TO_V4_0_AUTHORITY_EVIDENCE_MEMORY_PLAN.md)
