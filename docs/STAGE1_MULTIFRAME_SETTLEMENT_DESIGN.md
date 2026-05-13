# Stage 1 Multi-Frame Settlement Design

Status: benchmark design / not a certification claim

## Claim under test

```text
The harness can reduce premature one-path answers.
```

This is a Stage 1 settlement test only. It does not certify final DONE, does not prove general reasoning superiority, and does not prove the harness is safe for arbitrary autonomous goals.

Safe claim if the benchmark passes:

```text
The multi-frame harness reduced one-path collapse on this benchmark.
```

Unsafe claim:

```text
Multi-frame prompting is proven better for all reasoning tasks.
```

## A/B method

Use prompts where the obvious answer is incomplete.

For each prompt, compare two modes:

```text
A. normal_prompt
B. multiframe_harness
```

The initial implementation uses deterministic response fixtures. It does not call live models. Live model runs can be added later only after prompt provenance and run-local evidence capture are designed.

## Starter prompt set

The first settlement slice uses 5 prompts:

```text
Should I build an agent harness?
Is this paper idea novel?
Should I use Mercury V2 for coding?
Is this GitHub repo ready?
Should I add self-improvement to the harness now?
```

The full Stage 1 settlement should scale to 50 prompts after the deterministic skeleton is stable.

## Metrics

Per prompt and per mode:

```text
frame_count
assumption_count
failure_modes_found_count
rejected_bad_frames_count
alternative_recall
assumption_recall
failure_mode_recall
bad_frame_rejection_rate
quality_of_final_answer
composite_score
```

`quality_of_final_answer` is a deterministic fixture-backed proxy in the starter implementation. It is not a human-quality proof.

## Starter pass gate

For the 5-prompt starter gate:

```text
multiframe_harness must beat normal_prompt on at least 4 / 5 prompts
multiframe_harness must improve aggregate assumption recall
multiframe_harness must improve aggregate failure-mode recall
multiframe_harness must not reduce aggregate final-answer quality
```

This only settles the starter slice, not the full 50-prompt gate.

## Future 50-prompt gate

For the full gate:

```text
multiframe_harness beats normal_prompt on at least 35 / 50 prompts
assumption_recall improves by at least 20%
failure_mode_recall improves by at least 20%
quality_of_final_answer does not decrease
```

If this fails:

```text
Repair the frame generator first.
```

## Anti-gaming checks

The benchmark validator must reject:

```text
missing prompt modes
protected authority artifacts
final status values or claims
run_id whitespace or invisible characters
non-deterministic mode names
inconsistent pass-gate calculations
fixtures that omit expected target lists
```

The benchmark must not write:

```text
final_status.json
final_status.md
certification.json
policy_decision.json
```

## Authority boundary

This benchmark is evaluation-only.

```text
Pi can orchestrate.
Mercury can compile / execute / report.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

The Stage 1 evaluator reports benchmark metrics only. It cannot certify DONE.
