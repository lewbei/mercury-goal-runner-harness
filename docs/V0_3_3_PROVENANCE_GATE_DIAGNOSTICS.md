# v0.3.3 Provenance Gate Diagnostics

Owner: Mercury Goal Runner Harness
Status: source-of-truth
Last verified: 2026-05-07

## Claim

v0.3.3 tests this one claim:

```text
Self-generated or low-authority verifier evidence cannot certify DONE alone.
```

## Scope

This slice adds deterministic diagnostic fixtures and regression tests only.

It does not add:

- smell scanner
- strength scorer
- memory
- Pi integration
- more PlanGraph features
- broad diagnostic evaluation

## Fixture Layout

Each case under `.agentic-pi/diagnostics/provenance_gate/` is a copy-ready run folder:

```text
goal_contract.json
verifier_contract.json
step_logs/001.json
trace.jsonl
artifacts/output.txt
```

Verifier cases additionally include:

```text
verifier_artifacts/<verifier-id>.json
```

The missing-verifier case intentionally has no `verifier_artifacts/` directory.

## Cases

| Case | Meaning | Expected status |
|---|---|---|
| `case_p0_self_test` | same worker created solution and verifier | `PROVISIONAL_DONE` |
| `case_p1_existing_test` | local/public visible test only | `PROVISIONAL_DONE` |
| `case_p2_independent_test` | independent verifier artifact | `CERTIFIED_DONE` |
| `case_missing_verifier` | verifier contract exists but no verifier artifact | `NOT_DONE` |

## Executable Source Of Truth

The focused regression is:

```cmd
python tests\test_provenance_gate.py -v
```

The full acceptance command is:

```cmd
python -m unittest discover tests -v
```

## After v0.3.3

Only after this diagnostic slice passes:

```text
v0.3.4 = smell scanner
v0.3.5 = verifier strength scorer
v0.4 = small diagnostic evaluation
```
