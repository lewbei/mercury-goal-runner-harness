# Final Status: CERTIFIED_DONE

Run ID: `orchtest`

## Authority
- final_status_authority: certifier_only
- can_certify_done: false
Status source: `policy_decision.json`
Policy decision path: `policy_decision.json`
Certification path: `certification.json`
Generated at: 2026-05-10T09:39:58.567130+00:00

## Passed checks
- verifier_contract.json exists
- verifier_contract.json parses as JSON
- goal_contract.json exists
- goal_contract.json parses as JSON
- trace.jsonl exists
- trace.jsonl lines parse as JSON
- step_logs contain at least one step result
- 1.json evidence maps to touched files
- PlanGraph validation passed
- done_criteria is non-empty
- final_outputs is non-empty
- final output exists: is_prime.py
- Python module is_prime.py imports cleanly
- verifier target artifact exists: is_prime.py
- verifier_artifacts contain 2 artifact(s)
- verifier smell scan recorded: F.ORCHTEST
- verifier smell scan recorded: V.ORCHTEST
- verifier strength score recorded: F.ORCHTEST=gating
- verifier strength score recorded: V.ORCHTEST=certifying
- policy_decision.json validates
- policy engine status: CERTIFIED_DONE
- evidence_index.json validates
- evidence_freeze.json validates
- formal_verification: F_ORCHTEST PASS (confidence=0.50)
- crypto_signature: is_prime.py AUTHENTIC
- final_status.json validated

## Failed checks
- none

## Artifact hashes
- `is_prime.py`: `270a23d88e0c173c545d669122e57fe8ff9b74155983ef1fdb24e1bf335e257e`