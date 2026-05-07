# v0.3.2 Provenance Gate Freeze

Owner: Mercury Goal Runner Harness
Status: source-of-truth
Last verified: 2026-05-07

## Included

v0.3.2 includes:

- `verifier_artifact.schema.json`
- `verifier_contract.schema.json`
- `verifier_provenance.py`
- provenance-mode certifier statuses:
  - `NOT_DONE`
  - `PROVISIONAL_DONE`
  - `CERTIFIED_DONE`
- legacy compatibility for runs without `verifier_contract.json`
- rejection of Worker step logs that touch `verifier_artifacts/`
- automatic `P1` provenance logging for visible `artifact_tests`

## Not Included

v0.3.2 does not include:

- smell scanner
- strength scorer
- full policy YAML engine
- Pi integration
- real Mercury planner
- diagnostic evaluation benchmark
- SWE-bench, OpenHands, or mini-SWE-agent integration
- memory behavior

## Freeze Rule

```text
v0.3.2 = first runtime gate
not yet = full policy engine
not yet = smell scanner
not yet = strength scorer
```

The next slice is v0.3.3 Provenance Gate Diagnostic Tests. It should test the gate, not add more architecture.
