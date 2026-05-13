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

## What is captured

Each capture record stores one model output for one prompt and one mode:

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
