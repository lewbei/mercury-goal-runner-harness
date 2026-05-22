# Provenance Gate Diagnostics

Owner: Mercury Goal Runner Harness
Status: source-of-truth
Last verified: 2026-05-07

## Purpose

This is a small diagnostic set, not a benchmark.

It proves only the core provenance-gate claim:

```text
P0/P1 cannot certify final DONE.
P2/P3 can certify.
Missing verifier blocks completion.
```

## Cases

| Case | Meaning | Expected |
|---|---|---|
| `case_p0_self_test` | same worker created solution and verifier | `PROVISIONAL_DONE` |
| `case_p1_existing_test` | visible/local verifier only | `PROVISIONAL_DONE` |
| `case_p2_independent_test` | independent verifier | `CERTIFIED_DONE` |
| `case_missing_verifier` | verifier contract exists but no verifier artifact | `NOT_DONE` |

## Fixture Contract

Each case is a copy-ready run folder. The test copies each fixture into:

```text
.agentic-runs/test_<case_name>/
```

Then it runs:

```cmd
python .agentic-pi\validators\validator_factory.py .agentic-runs\test_<case_name>
python .agentic-pi\validators\certify_run.py .agentic-runs\test_<case_name>
```

and reads `final_status.md`.

## Source Of Truth

The executable check is:

```cmd
python -m unittest discover tests -v
```

The focused test file is:

```text
tests/test_provenance_gate.py
```
