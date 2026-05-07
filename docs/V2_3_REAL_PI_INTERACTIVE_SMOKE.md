# v2.3 Real Pi Interactive Smoke

```text
REAL PI INTERACTIVE SMOKE EVIDENCE RECORDED
```

v2.3 records the first real interactive Pi smoke result.

The corrected framing is:

```text
pi = the real external Pi agent launched from cmd.
Mercury = the LLM behavior inside Pi.
.agentic-pi/runtime/pi_cli.py = repo-local deterministic harness helper, not Pi.
```

The core invariant is unchanged:

```text
Who is allowed to certify DONE?
Strategy can suggest.
Planner can select.
Memory can suggest.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

## Implemented Files

```text
.agentic-pi/diagnostics/pi_real_interactive/prompts/real_pi_chain_smoke_prompt.txt
.agentic-pi/diagnostics/pi_real_interactive/transcripts/real_pi_chain_smoke_result.txt
tests/test_pi_real_interactive_smoke_docs.py
docs/V2_3_REAL_PI_INTERACTIVE_SMOKE.md
```

## What Was Tested

The operator launched the real Pi agent from cmd:

```cmd
pi
```

Then the operator pasted the v2.3 prompt from:

```text
.agentic-pi/diagnostics/pi_real_interactive/prompts/real_pi_chain_smoke_prompt.txt
```

The prompt required Mercury inside Pi to:

```text
run exactly one controlled smoke command
read pi_chain_runtime_result.json
report only requested fields
not certify DONE itself
```

The exact allowed command was:

```cmd
python .agentic-pi/runtime/run_pi_chain_smoke.py --live --clean --target-run-id pi_smoke_real_interactive_p2_strong
```

The exact required result file was:

```text
.agentic-runs/pi_chain_smoke_outputs/pi_chain_runtime_result.json
```

## Observed Result

The transcript fixture records:

```text
result_status: PASS
status_values:
{"final_status.md":"CERTIFIED_DONE","certification.json":"CERTIFIED_DONE","policy_decision.json":"CERTIFIED_DONE"}
status_artifacts_agree: true
final_status_authority: certifier_only
can_certify_done: false
claim_boundary: Controlled Pi chain smoke only; not proof of arbitrary autonomous goal-runner.chain.md runtime
```

## What v2.3 Proves

```text
A real Pi/Mercury interactive smoke can follow the verifier-provenance reporting contract on a controlled disposable run.
Mercury can invoke the deterministic harness command through Pi.
Mercury can read the certifier-owned output artifact.
Mercury can report artifact values without claiming certification authority.
```

## What v2.3 Does Not Prove

```text
It does not prove arbitrary Pi autonomy.
It does not prove full goal-runner.chain.md runtime.
It does not prove live worker execution.
It does not prove repair behavior after NOT_DONE or PROVISIONAL_DONE.
It does not prove Mercury can certify DONE.
```

## Evidence Boundary

This is local smoke evidence, not automated CI evidence.

The tested smoke can be replayed manually by launching:

```cmd
pi
```

and pasting:

```text
.agentic-pi/diagnostics/pi_real_interactive/prompts/real_pi_chain_smoke_prompt.txt
```

Safe claim:

```text
A real Pi/Mercury interactive smoke can follow the verifier-provenance reporting contract on a controlled disposable run.
```

Unsafe claim:

```text
Full autonomous Pi goal-runner runtime is proven.
Mercury can certify DONE.
```

Both unsafe claims remain false.
