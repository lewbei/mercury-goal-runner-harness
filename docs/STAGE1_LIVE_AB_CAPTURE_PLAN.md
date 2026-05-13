# Stage 1 Live A/B Capture Plan

Status: provenance-capture scaffold / not live evidence / not certification

## Purpose

The deterministic 50-prompt Stage 1 benchmark is fixture-scored. The next stronger evidence layer is to capture real outputs for both modes:

```text
normal_prompt
multiframe_harness
```

This live A/B capture layer validates provenance and completeness only. It does not call live models, does not score raw text automatically, and does not certify DONE.

## Authority boundary

```text
Pi can orchestrate.
Mercury can compile / execute / report.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

The live capture validator has:

```text
authority_level = evaluation_capture_only
can_certify_done = false
final_status_authority = certifier_only
```

## Request pack

Before live capture, generate a deterministic request pack:

```cmd
python .agentic-pi\evaluation\stage1_multiframe\generate_live_capture_request_pack.py --output .agentic-pi\evaluation\stage1_multiframe\live_capture_request_pack_v2.json
python .agentic-pi\evaluation\stage1_multiframe\validate_live_capture_request_pack.py --request-pack .agentic-pi\evaluation\stage1_multiframe\live_capture_request_pack_v2.json
```

The request pack contains 100 tasks:

```text
50 prompts × 2 modes = 100 capture tasks
```

It contains prompt text, prompt hashes, mode-specific instructions, required return fields, and forbidden actions. It does **not** contain model outputs, output hashes, provider responses, or live evidence.

The v2 multi-frame request adds grounding discipline: known facts from the prompt, assumptions labeled as prompt-supported or speculative, unknowns, claims needing evidence, weak-path attacks, rejected bad frames, and a final direction that separates supported conclusions from unknowns.

## Mercury subset capture

A small Mercury subset can be captured through the Pi CLI before attempting the full 50-prompt run:

```cmd
python .agentic-pi\evaluation\stage1_multiframe\run_mercury_live_capture.py --prompt-limit 5 --output .agentic-pi\evaluation\stage1_multiframe\live_capture_mercury_subset_5_v2.json
python .agentic-pi\evaluation\stage1_multiframe\validate_stage1_live_capture.py --capture .agentic-pi\evaluation\stage1_multiframe\live_capture_mercury_subset_5_v2.json --allow-subset-for-tests
```

This uses `pi --model inception/mercury-2 --no-tools --no-session`. Pi CLI does not expose temperature, max output tokens, or provider request id in this path, so those runtime parameters are recorded as unavailable rather than guessed.

This subset is live Mercury capture evidence, but it is still not full Stage 1 settlement evidence.

## What is captured

Each completed capture record stores one model output for one prompt and one mode:

```text
prompt_id
mode
provider
model
model_version
prompt_text
prompt_hash
system_prompt_hash
output_text
output_hash
captured_at
capture_method
provenance
```

Hashes are SHA-256 over the exact UTF-8 text stored in the artifact.

## Full vs subset capture

Default validation requires all 50 benchmark prompts and exactly two captures per prompt.

For unit tests and small dry runs only:

```text
--allow-subset-for-tests
```

This requires:

```text
capture_scope = subset_fixture_only
```

Subset captures cannot be used for the Stage 1 settlement claim.

## What this does not do

This layer does not extract frames, assumptions, failure modes, or rejected bad frames from raw model text. That needs a separate extraction/scoring protocol.

It also does not make this claim:

```text
The live model A/B benchmark passed.
```

It can only say:

```text
The live A/B capture artifact passed provenance and completeness validation.
```

## Fail-closed checks

The validator rejects:

```text
missing prompt IDs
missing normal/multiframe mode pair
duplicate mode per prompt
prompt text mismatch
prompt hash mismatch
output hash mismatch
missing provider/model/version metadata
can_certify_done: true
final status values like CERTIFIED_DONE or DONE_PASS
protected artifact references like final_status.json
full validation with subset_fixture_only
subset validation without --allow-subset-for-tests
```

## Later extraction step

A future extraction protocol may convert validated raw outputs into structured fields:

```text
frames_found
assumptions_found
failure_modes_found
bad_frames_rejected
quality_of_final_answer
```

That extraction protocol must itself have provenance, validators, and anti-gaming checks before its scores can be compared to the deterministic fixture benchmark.
