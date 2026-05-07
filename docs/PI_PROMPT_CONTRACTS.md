# Pi Prompt Contracts

This document records safe prompt patterns for the v0.5 Pi integration path.

The goal is to keep Pi orchestration narrow while preserving the main authority
rule:

```text
Pi can orchestrate.
Mercury can compile/execute/report.
certify_run.py + policy_engine.py decide final status.
```

## Core rule

```text
One prompt = one action.
```

Do not mix:

```text
copy
repair
certify
summarize
infer
```

in the same prompt.

## Status reporting prompt

Good:

```text
Read these exact files now:
.agentic-runs/<run_id>/final_status.md
.agentic-runs/<run_id>/certification.json
.agentic-runs/<run_id>/policy_decision.json

Report the status from each file. If any file is missing, say MISSING.
Do not certify DONE yourself. Final status comes only from certify_run.py.
```

Bad:

```text
Check the run, decide if it is done, repair anything missing, then summarize.
```

## Certifier invocation prompt

Good:

```text
Run only this command, then read final_status.md, certification.json, and
policy_decision.json from the same run folder:
python .agentic-pi/validators/certify_run.py .agentic-runs/<run_id>

Do not edit any files manually. Do not certify DONE yourself.
Final status comes only from certify_run.py.
```

For Pi bash prompts, use forward slashes. Backslash-to-forward-slash retry
behavior counts as more than one certifier command and fails v0.5.9 command
discipline audit.

Bad:

```text
Prepare a run, fix broken artifacts, run certification, repair failures, and
tell me whether the goal is done.
```

## Failure behavior

If certifier output is:

```text
NOT_DONE
PROVISIONAL_DONE
DONE_FAIL
```

then the Pi agent may report that status, but it must not repair the run unless
the user explicitly asks for repair mode.

If a status file is missing, the Pi agent must say:

```text
MISSING
```

It must not infer a replacement status.

## Forbidden prompt behavior

Do not ask Pi agents to:

```text
certify DONE themselves
upgrade PROVISIONAL_DONE to CERTIFIED_DONE
edit final_status.md
edit certification.json
edit policy_decision.json
forge verifier_artifacts
claim self-generated evidence is independent
run hidden multi-step autonomy
```

The short version is:

```text
Do one action. Report certifier artifacts. Do not certify DONE yourself.
```
