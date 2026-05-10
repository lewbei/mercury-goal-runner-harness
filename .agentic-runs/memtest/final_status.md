# Final Status: CERTIFIED_DONE

Run ID: `memtest`

## Authority
- final_status_authority: certifier_only
- can_certify_done: false
Status source: `policy_decision.json`
Policy decision path: `policy_decision.json`
Certification path: `certification.json`
Generated at: 2026-05-10T09:10:33.401499+00:00

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
- final output exists: validate_email.py
- Python script validate_email.py produced >=2 lines of output
- verifier target artifact exists: validate_email.py
- verifier_artifacts contain 2 artifact(s)
- verifier smell scan recorded: F.MEMTEST
- verifier smell scan recorded: V.MEMTEST
- verifier strength score recorded: F.MEMTEST=gating
- verifier strength score recorded: V.MEMTEST=certifying
- policy_decision.json validates
- policy engine status: CERTIFIED_DONE
- evidence_index.json validates
- evidence_freeze.json validates
- formal_verification: F_MEMTEST PASS (confidence=0.50)
- crypto_signature: validate_email.py AUTHENTIC
- final_status.json validated

## Failed checks
- none

## Artifact hashes
- `validate_email.py`: `9a5693f1a9c50d3c6bfb4d295d295074f93ebda14db3fb94a1df2b15d8b85987`