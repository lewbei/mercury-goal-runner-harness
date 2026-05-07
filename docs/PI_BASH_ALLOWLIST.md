# Pi Bash Allowlist

This document records the v0.5 bash safety contract for `goal-orchestrator`.

It is documentation-only for now. It is not yet a deterministic runtime
allowlist implementation.

## Default allowed commands

The default safe command surface is read/list plus deterministic certification.

Allowed:

```text
python .agentic-pi\validators\certify_run.py .agentic-runs\<run_id>
```

Allowed read/list operations:

```text
read final_status.md
read certification.json
read policy_decision.json
ls .agentic-runs\<run_id>
dir .agentic-runs\<run_id>
type .agentic-runs\<run_id>\final_status.md
Get-Content .agentic-runs\<run_id>\final_status.md
```

The certifier may write:

```text
final_status.md
certification.json
policy_decision.json
verifier_smell_reports/
verifier_strength_reports/
```

Pi agents must not write those files manually.

## Disposable smoke setup

Disposable setup is allowed only when the prompt explicitly names a
`.agentic-runs/pi_smoke_*` folder.

Allowed only for explicitly named disposable smoke folders:

```text
copy an existing diagnostic run into .agentic-runs/pi_smoke_*
remove .agentic-runs/pi_smoke_* before recreating it
replace copied run_id text inside .agentic-runs/pi_smoke_*
remove generated certifier outputs inside .agentic-runs/pi_smoke_* before rerun
```

This permission does not apply to normal run folders.

## Forbidden commands and actions

Forbidden:

```text
manual edit of final_status.md
manual edit of certification.json
manual edit of policy_decision.json
manual edit of verifier_artifacts/
manual edit of verifier_smell_reports/
manual edit of verifier_strength_reports/
deletion outside explicitly named .agentic-runs/pi_smoke_* folders
repair after NOT_DONE unless the user explicitly requests repair mode
git reset
git clean
git push
```

Also forbidden:

```text
del or rm against broad paths
move or mv against non-disposable run folders
commands that rewrite repo source files
commands that make Worker-authored verifier evidence look independent
```

## Safe claim

The current safe claim is:

```text
goal-orchestrator may invoke the deterministic certifier on an existing or
explicitly disposable run folder.
```

The current unsafe claim is:

```text
goal-orchestrator may freely use bash to repair or certify runs.
```

