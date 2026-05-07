# v0.3.5 Strength Scorer

Owner: Mercury Goal Runner Harness
Status: source-of-truth
Last verified: 2026-05-07

## Claim

v0.3.5 tests this one claim:

```text
Even if a verifier is P2, it still needs enough strength to be treated as certifying evidence later.
```

## Scope

This slice scores verifier strength and records strength reports only.

It does not:

- enforce policy,
- change final certification status,
- consume `certification_policy.yaml`,
- add Pi integration,
- add memory,
- add more PlanGraph features,
- or run a broad diagnostic evaluation.

## Scorer

The scorer lives at:

```text
.agentic-pi/validators/strength_scorer.py
```

It reads verifier provenance metadata plus smell reports and emits:

```json
{
  "artifact_id": "V.P2_INDEPENDENT",
  "run_id": "test_case_p2_independent_test",
  "score": 11,
  "strength_level": "certifying",
  "positive_factors": [
    "executes_target_artifact",
    "has_assertions",
    "multiple_assertions",
    "p2_or_p3_authority",
    "independent_authority",
    "pre_solution_or_preexisting"
  ],
  "penalties": [],
  "smell_flags_used": []
}
```

The report schema is:

```text
.agentic-pi/schemas/verifier_strength_report.schema.json
```

## Positive Points

```text
+2 executes target artifact
+2 assertion_count > 0
+2 assertion_count >= 2
+2 provenance_level is P2 or P3
+2 source is independent_verifier_agent / user_provided / hidden_oracle / external_benchmark / human_review
+1 created_at_phase is pre_solution or external_preexisting
```

## Penalties

```text
-3 same_worker_self_test
-3 p0_self_authored
-2 post_solution_test
-2 depends_on_solution
-2 does_not_execute_code
-2 zero_assertions
-2 file_existence_only
-2 exit_code_only
-2 print_only_observation
-2 mock_heavy
-3 implementation_coupled_oracle
```

## Strength Bands

```text
score <= 1   = weak
score 2 to 4 = advisory
score 5 to 7 = gating
score >= 8   = certifying
```

## Critical Caps

The scorer also applies deterministic caps for evidence that should not remain certifying by score arithmetic alone:

```text
does_not_execute_code -> max weak
zero_assertions -> max advisory
mock_heavy -> max gating
implementation_coupled_oracle -> max advisory
```

These caps are strength classification only. They are not final policy enforcement.

## Certifier Boundary

`certify_run.py` records strength reports under:

```text
verifier_strength_reports/
```

v0.3.5 does not make strength reports change final status yet.

That means:

```text
v0.3.5 = score verifier strength
not yet = enforce policy
not yet = change NOT_DONE / PROVISIONAL_DONE / CERTIFIED_DONE decisions
```

## Acceptance

The executable source of truth is:

```cmd
python tests\test_strength_scorer.py -v
python -m unittest discover tests -v
```

The scorer must show:

```text
P0 self-test -> weak or advisory
P1 existing visible test -> advisory or gating
P2 independent verifier -> certifying
zero-assertion verifier -> weak/advisory
mock-heavy verifier -> downgraded
All v0.3.4 tests still pass.
```

## Next

The next slice is:

```text
v0.3.6 = Policy Engine
```

That slice will consume `certification_policy.yaml`, smell reports, strength reports, verifier artifacts, and verifier contracts.
