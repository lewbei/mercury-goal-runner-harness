# v2.6 Real Pi Session Trace Capture

```text
REAL PI SESSION TRACE CAPTURE IMPLEMENTED
```

v2.6 fixes the awkward part of the v2.3-v2.5 workflow:

```text
manual transcript text is useful for smoke testing,
but trace log becomes the source of truth.
```

The invariant remains:

```text
Who is allowed to certify DONE?
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
Final status still comes only from certify_run.py and policy_engine.py.
```

## Implemented Files

```text
.agentic-pi/runtime/pi_session_trace_monitor.py
.agentic-pi/runtime/run_real_pi_trace_smoke.py
.agentic-pi/schemas/pi_session_trace_event.schema.json
.agentic-pi/schemas/pi_session_trace_monitor.schema.json
tests/test_pi_session_trace_capture.py
docs/V2_6_REAL_PI_SESSION_TRACE_CAPTURE.md
```

## Trace Shape

Each controlled Pi smoke can now write:

```text
.agentic-runs/<run_id>/pi_session_raw_output.txt
.agentic-runs/<run_id>/pi_session_trace.jsonl
.agentic-runs/<run_id>/pi_session_monitor_result.json
```

The live path uses Pi's JSON event stream:

```cmd
pi --mode json -p "<single-action prompt>"
```

The offline path can still ingest copied terminal transcripts. Both paths normalize
into the same trace shape.

The trace records normalized events:

```text
bash_command
read_file
reported_field
reported_status_mention
assistant_text
tool_call
```

The monitor audits the JSONL trace for:

```text
exactly one allowed bash command
required status/result reads after bash
no unexpected reads
no unauthorized non-read/non-bash tool calls
no protected status or verifier artifact writes
status artifacts agree
final_status_authority = certifier_only
can_certify_done = false
no assistant-side status upgrade
no self-certifying assistant language
```

## Live Command

For a real Pi-backed trace smoke:

```cmd
python .agentic-pi\runtime\run_real_pi_trace_smoke.py --case p2_strong --live --clean --target-run-id pi_smoke_trace_p2_strong
```

For weak/failing status smokes:

```cmd
python .agentic-pi\runtime\run_real_pi_trace_smoke.py --case p1_visible --live --clean --target-run-id pi_smoke_trace_p1_visible
python .agentic-pi\runtime\run_real_pi_trace_smoke.py --case missing_verifier --live --clean --target-run-id pi_smoke_trace_missing_verifier
```

The prompt used by the live runner is intentionally single-line because earlier
multi-line non-interactive Pi prompts were fragile under Windows command
invocation. The runner also tells Pi not to use `ls`, `grep`, `find`, `edit`,
`write`, or extra bash commands.

## Offline Fixture Command

For deterministic tests without invoking Pi:

```cmd
python .agentic-pi\runtime\run_real_pi_trace_smoke.py --case p1_visible --target-run-id pi_smoke_trace_fixture_p1 --from-transcript .agentic-pi\diagnostics\pi_real_interactive\session_fixtures\positive_real_pi_provisional.txt
```

## What v2.6 Proves

```text
Captured Pi stdout/transcripts can be normalized into pi_session_trace.jsonl.
Pi JSON event stream output can be normalized into pi_session_trace.jsonl.
The JSONL trace can be monitored directly.
PROVISIONAL_DONE and NOT_DONE can be preserved from trace evidence.
Assistant-side upgrades such as PROVISIONAL_DONE -> CERTIFIED_DONE fail.
The trace monitor cannot certify DONE.
```

## What v2.6 Does Not Prove

```text
It does not prove arbitrary Pi autonomy.
It does not prove full goal-runner.chain.md runtime.
It does not prove live worker execution.
It does not prove repair behavior.
It does not prove Mercury semantic planning quality.
```

Safe claim:

```text
Real Pi smoke output can be normalized into an auditable session trace, and that trace can be checked for certifier-only status reporting.
```

Unsafe claim:

```text
Pi can certify DONE by itself.
```

That remains false.
