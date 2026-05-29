# Agent Instructions

## Quick Start (any agent)

When the user asks you to build something, use the Mercury harness:

```bash
python mercury.py run "what the user wants to build"
```

Check status:
```bash
python mercury.py status <run_id>
```

Health check:
```bash
python mercury.py health
```

## Rules

1. Product files go to `output/<app-name>/`
2. Do NOT edit `.agentic-pi/` or `.agentic-runs/`
3. Do NOT claim DONE — the certifier decides
4. Trust evidence, not vibes

## User Operating Rules

Do not simplified the code. Always be honest. You must always use my sentences
so that my voice always there. Please guide me and be honest with me. You are
an expert who double checks things, you are skeptical and you do research. I am
not always right. Neither are you but we both strive for accuracy. You need to
confirm everything before u proceed the next step. Have a team of agents to
discuss.

## Core Harness Invariant

```text
Who is allowed to certify DONE?
Pi can orchestrate.
Mercury can compile / execute / report.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

Agents may plan, execute, repair, summarize, and report evidence. Agents may
not certify DONE. Final status comes only from `certify_run.py` /
`policy_engine.py` and their owned status artifacts.

## Pi / Mercury Implementation Rules

These rules exist because Pi/Mercury can make plausible-looking implementation
mistakes. Do not trust an agent because it says PASS. Trust file layout checks,
validators, proof matrix entries, and regression tests.

Allowed implementation paths by default:

```text
.agentic-pi/
.pi/
docs/
tests/
README.md
PROJECT_STATUS.md
FRAMEWORK.md
workspace_index.md
AGENTS.md
```

Forbidden by default:

```text
top-level implementation packages
top-level conftest.py
pytest-only tests for new harness slices
new root-level runtime packages
direct imports from modules/ace-main
direct imports from modules/mempalace-develop
copying or vendoring modules/ace-main
copying or vendoring modules/mempalace-develop
manual edits to final_status.json
manual edits to final_status.md
manual edits to certification.json
manual edits to policy_decision.json
```

Use `unittest`-style tests for this repo unless a specific existing slice
already requires something else.

If a task requires files outside the allowed paths, stop and report:

```text
BLOCKED: requested edit path is outside the harness implementation boundary.
```

## Reference Module Boundary

The local folders below are reference material only:

```text
modules/ace-main/
modules/mempalace-develop/
modules/nagini-develop/
```

Agents may read them to understand design ideas. Agents must not import from
them, depend on them, copy them, vendor them, or turn them into harness runtime
dependencies. Implement a better harness-native version under `.agentic-pi/`.

For formal verification, the harness-native implementation lives at:
`.agentic-pi/formal/harness_contract_verifier.py` — parses `#@ Requires/Ensures`
annotations, evaluates contracts at runtime, produces `F_{RUN_ID}.json` evidence.

For cryptographic signing, the harness-native implementation lives at:
`.agentic-pi/formal/harness_signing.py` — Ed25519 keypairs, artifact signing
with `.sig` files, content-hash verification to detect tampering.

For subagent memory, the harness-native pipeline lives at:
`.agentic-pi/runtime/run_subagent_memory.py` — captures learnings per subagent
into `.agentic-pi/memory/durable/` (project-local, not MCP-dependent).

## Required Post-Implementation Audit

After any Pi/Mercury implementation attempt, run focused checks before claiming
success:

```cmd
python tests\test_repo_structure_cleanup.py -v
git diff --check
git status -sb
```

For milestone work, also run the focused tests for that milestone and the quick
proof matrix when the milestone is wired into `.agentic-pi/proof_matrix/`.

## Anti-Overclaim Rule

Safe claim:

```text
The harness passed the listed deterministic validators and proof commands.
```

Unsafe claim:

```text
Pi/Mercury is proven safe for arbitrary autonomous goals.
```

Do not make the unsafe claim.
