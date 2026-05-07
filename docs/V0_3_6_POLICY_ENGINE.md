# v0.3.6 Policy Engine

v0.3.6 is the first deterministic policy enforcement slice for the verifier-provenance direction.

It answers:

```text
Given the verifier provenance, smell report, strength report, and verifier contract,
is this run NOT_DONE, PROVISIONAL_DONE, or CERTIFIED_DONE?
```

## What v0.3.6 Adds

- `.agentic-pi/runtime/policy_engine.py`
- `.agentic-pi/schemas/policy_decision.schema.json`
- `policy_decision.json` written inside provenance-mode run folders
- certifier integration that uses the policy decision as the final provenance-mode status
- tests for P0, P1, P2, missing verifier, weak P2, and policy-decision schema validation

## Policy Table

| Evidence condition | Status |
| --- | --- |
| Target artifact missing | `NOT_DONE` |
| Verifier contract exists but no verifier artifact exists | `NOT_DONE` |
| P0 evidence only | `PROVISIONAL_DONE` |
| P1 evidence only | `PROVISIONAL_DONE` |
| P2/P3 evidence with weak, advisory, or gating strength | `PROVISIONAL_DONE` |
| P2/P3 evidence with certifying strength and no disqualifying smell | `CERTIFIED_DONE` |
| `allow_self_generated_only=true` while P2/P3 is required | `NOT_DONE` |
| Any hard validation failure before policy decision | `NOT_DONE` |

## Boundary

v0.3.6 consumes:

- `verifier_contract.json`
- `verifier_artifacts/*.json`
- `verifier_smell_reports/*.json`
- `verifier_strength_reports/*.json`
- hard validation failures already found by the certifier

It does not:

- generate verifier artifacts
- generate tests
- run Pi agents
- add memory behavior
- expand benchmarks
- claim true oracle quality

The strength scorer remains a heuristic strength estimate. The policy engine only enforces the current harness rule:

```text
Self-generated or low-authority verifier evidence cannot certify DONE alone.
```

## Compatibility

Legacy runs without `verifier_contract.json` still use:

```text
DONE_PASS
DONE_FAIL
```

Provenance-mode runs with `verifier_contract.json` use:

```text
NOT_DONE
PROVISIONAL_DONE
CERTIFIED_DONE
```

## Acceptance

```cmd
python tests\test_policy_engine.py -v
python -m unittest discover tests -v
python .agentic-pi\benchmark\run_benchmark.py
```

Expected policy behavior:

```text
P0 -> PROVISIONAL_DONE
P1 -> PROVISIONAL_DONE
P2 strong -> CERTIFIED_DONE
missing verifier -> NOT_DONE
P2 weak -> PROVISIONAL_DONE
P2/P3 required with allow_self_generated_only=true -> NOT_DONE
```
