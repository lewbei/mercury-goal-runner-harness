# Provenance Gate Diagnostic Report

Generated: 2026-05-07

## Claim Tested

```text
Can verifier provenance alone prevent self-certified DONE?
```

## Source Of Truth

Executable test:

```cmd
python tests\test_provenance_gate.py -v
```

The test copies each diagnostic fixture into `.agentic-runs/test_<case_name>/`, runs `certify_run.py`, then reads `final_status.md`.

Result:

```text
Ran 4 tests
OK
```

Full regression check:

```cmd
python -m unittest discover tests -v
```

Result:

```text
Ran 38 tests
OK
```

## Case Results

| Case | Expected | Verified |
|---|---|---|
| `case_p0_self_test` | `PROVISIONAL_DONE` | yes |
| `case_p1_existing_test` | `PROVISIONAL_DONE` | yes |
| `case_p2_independent_test` | `CERTIFIED_DONE` | yes |
| `case_missing_verifier` | `NOT_DONE` | yes |

## Interpretation

This diagnostic set verifies only the first provenance gate:

```text
P0/P1 cannot certify final DONE.
P2/P3 can certify.
Missing verifier blocks completion.
```

It does not test smell scanning, strength scoring, Pi integration, real Mercury execution, or hidden benchmark behavior.
