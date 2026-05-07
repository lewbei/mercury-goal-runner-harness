# v0.3.4 Smell Scanner

Owner: Mercury Goal Runner Harness
Status: source-of-truth
Last verified: 2026-05-07

## Claim

v0.3.4 tests this one claim:

```text
Verifier artifacts can carry weak-evidence smells that should be recorded before later strength scoring or policy enforcement.
```

## Scope

This slice adds metadata-level smell detection only.

It does not add:

- verifier strength scoring
- full policy-engine enforcement
- Pi integration
- memory
- more PlanGraph features
- broad diagnostic evaluation

## Scanner

The scanner lives at:

```text
.agentic-pi/validators/smell_scanner.py
```

It reads verifier provenance artifact metadata and emits:

```json
{
  "artifact_id": "V.P0_SELF",
  "smell_flags": [
    "same_worker_self_test",
    "post_solution_test",
    "depends_on_solution"
  ],
  "disqualifying": false,
  "authority_penalty": 4
}
```

The report schema is:

```text
.agentic-pi/schemas/verifier_smell_report.schema.json
```

## Initial Smells

The v0.3.4 scanner detects:

```text
same_worker_self_test
post_solution_test
depends_on_solution
does_not_execute_code
zero_assertions
mock_heavy
p0_self_authored
advisory_only
local_visible_verifier
gating_only
file_existence_only
exit_code_only
print_only_observation
grep_or_source_text_check
no_negative_case
implementation_coupled_oracle
placeholder_text_check
```

Some flags are metadata-native. Others are pass-through flags from the verifier artifact's own `smell_flags` field until command/test-content inspection exists.

## Certifier Boundary

`certify_run.py` records smell reports under:

```text
verifier_smell_reports/
```

v0.3.4 does not make smell reports change final status yet.

That means:

```text
v0.3.4 = detect and record smells
not yet = score verifier strength
not yet = enforce smell policy
```

## Acceptance

The executable source of truth is:

```cmd
python tests\test_smell_scanner.py -v
python -m unittest discover tests -v
```

The scanner must show:

```text
P0 self-test gets smell flags.
P1 visible verifier gets weaker warning flags.
P2 independent verifier gets no critical smell.
zero-assertion verifier gets zero_assertions.
mock-heavy verifier gets mock_heavy.
All v0.3.3 tests still pass.
```
