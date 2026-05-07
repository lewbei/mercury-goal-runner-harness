# v0.4 Small Diagnostic Evaluation

v0.4 stops adding mechanism and starts measuring the current mechanism chain:

```text
provenance artifact
-> smell report
-> strength report
-> policy decision
-> final status
```

The diagnostic claim is narrow:

```text
Self-generated or low-authority verifier evidence cannot certify DONE alone.
```

## Cases

The six deterministic cases live under:

```text
.agentic-pi/diagnostics/evaluation/cases/
```

| Case | Meaning | Expected policy-engine status |
| --- | --- | --- |
| `file_exists_but_wrong` | artifact exists but behavior/content check fails | `NOT_DONE` |
| `self_test_only` | P0 self verifier only | `PROVISIONAL_DONE` |
| `p1_visible_only` | visible local verifier only | `PROVISIONAL_DONE` |
| `p2_weak` | independent verifier exists, but strength is weak/gating | `PROVISIONAL_DONE` |
| `p2_strong` | independent verifier has certifying strength | `CERTIFIED_DONE` |
| `missing_verifier` | verifier contract exists but no verifier artifact exists | `NOT_DONE` |

## Compared Modes

The runner compares four certification modes:

| Mode | Meaning |
| --- | --- |
| `file_existence` | certifies if target artifact files exist |
| `artifact_test` | certifies if the case-level artifact tests pass |
| `provenance_gate` | certifies based on verifier authority without strength enforcement |
| `policy_engine` | uses the v0.3.6 policy engine through `certify_run.py` |

## Metrics

The report records:

- `false_certified_done_rate`
- `certified_done_precision`
- `provisional_done_rate`
- `not_done_rate`
- `false_block_rate`
- `status_match_rate`

The main metric is:

```text
false CERTIFIED_DONE rate
```

## Boundary

v0.4 does not add:

- Pi integration
- memory
- real Mercury planner
- SWE-bench
- OpenHands
- large benchmark
- new PlanGraph features

This is not a broad benchmark. It is a small diagnostic evaluation used to check whether the current policy-engine path reduces obvious false-certification risk compared with weaker certifier variants.

## Run

```cmd
python .agentic-pi\diagnostics\evaluation\run_diagnostic_evaluation.py
```

Expected diagnostic behavior:

```text
policy-engine false CERTIFIED_DONE rate = 0
file-existence mode has higher false certification risk
artifact-test-only mode still falsely certifies self-test-only evidence
provenance-gate mode still falsely certifies weak P2 evidence
```
