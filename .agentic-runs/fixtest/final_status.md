# Final Status: CERTIFIED_DONE

Run ID: `fixtest`

## Authority
- final_status_authority: certifier_only
- can_certify_done: false
Status source: `policy_decision.json`
Policy decision path: `policy_decision.json`
Certification path: `certification.json`
Generated at: 2026-05-10T09:19:38.909365+00:00

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
- final output exists: factorial.py
- Python module factorial.py imports cleanly
- verifier target artifact exists: factorial.py
- verifier_artifacts contain 2 artifact(s)
- verifier smell scan recorded: F.FIXTEST
- verifier smell scan recorded: V.FIXTEST
- verifier strength score recorded: F.FIXTEST=gating
- verifier strength score recorded: V.FIXTEST=certifying
- policy_decision.json validates
- policy engine status: CERTIFIED_DONE
- evidence_index.json validates
- evidence_freeze.json validates
- formal_verification: F_FIXTEST PASS (confidence=0.50)
- crypto_signature: factorial.py AUTHENTIC
- final_status.json validated

## Failed checks
- none

## Artifact hashes
- `factorial.py`: `7361e41b67937bf43ccbaa719740429f850ad73a4454bb0e9d55454e0a713dec`