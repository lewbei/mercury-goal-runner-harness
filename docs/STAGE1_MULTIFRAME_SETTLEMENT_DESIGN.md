# Stage 1 Multi-Frame Settlement Design

Status: deterministic benchmark design / not a certification claim

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

The current implementation uses deterministic response fixtures. It does not call live models. Live model runs can be added later only after prompt provenance and run-local evidence capture are designed.

## Prompt set

The benchmark now has 50 deterministic fixture prompts. The original 5 starter prompts are preserved inside the 50-prompt set:

```text
Should I build an agent harness?
Is this paper idea novel?
Should I use Mercury V2 for coding?
Is this GitHub repo ready?
Should I add self-improvement to the harness now?
```

## Category distribution

The 50 prompts are category-balanced for this harness stage:

```text
harness_governance:             8
coding_tool_use:                7
research_paper_novelty:         7
repo_product_readiness:         6
model_routing:                  6
self_improvement_evolution:     5
memory_reputation_trust:        5
safety_security:                3
ambiguous_user_intent:          3
```

Each prompt includes:

```text
prompt_id
category
difficulty
trap_type
prompt
obvious_answer_trap
expected_frames
expected_assumptions
expected_failure_modes
bad_frames_to_reject
```

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

`quality_of_final_answer` is a deterministic fixture-backed proxy. It is not a human-quality proof.

## Starter pass gate

For a 5-prompt starter fixture, the starter gate is:

```text
multiframe_harness must beat normal_prompt on at least 4 / 5 prompts
multiframe_harness must improve aggregate assumption recall
multiframe_harness must improve aggregate failure-mode recall
multiframe_harness must not reduce aggregate final-answer quality
```

When the fixture has 50 prompts, the starter gate is marked:

```text
NOT_APPLICABLE
```

## 50-prompt settlement gate

For the 50-prompt fixture:

```text
multiframe_harness beats normal_prompt on at least 35 / 50 prompts
assumption_recall relative improvement is at least 20%
failure_mode_recall relative improvement is at least 20%
quality_of_final_answer does not decrease
```

The report field is:

```text
settlement_50_gate.status = SETTLEMENT_50_PASS | SETTLEMENT_50_FAIL
```

If this fails:

```text
Repair the frame generator first.
```

## Anti-gaming checks

The benchmark validator must reject:

```text
missing prompt modes
duplicate prompt modes
wrong prompt count other than 5 or 50
wrong 50-prompt category distribution
missing categories
protected authority artifacts
final status values or claims
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

## Honest limitation

This 50-prompt fixture is still deterministic and hand-authored. It is stronger than the 5-prompt starter skeleton, but it is not yet live-model evidence. A later live A/B run must capture prompt provenance, model metadata, outputs, and scoring artifacts before any stronger empirical claim.

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
