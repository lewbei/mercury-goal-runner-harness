# Final Status: DONE_FAIL

Run ID: `agentfix`

## Authority
- final_status_authority: certifier_only
- can_certify_done: false
Status source: `certification.json`
Policy decision path: ``
Certification path: `certification.json`
Generated at: 2026-05-10T10:25:09.307440+00:00

## Passed checks
- goal_contract.json exists
- goal_contract.json parses as JSON
- trace.jsonl exists
- trace.jsonl lines parse as JSON
- step_logs contain at least one step result
- 1.json evidence maps to touched files
- PlanGraph validation passed
- done_criteria is non-empty
- final_outputs is non-empty
- final output exists: reverse_string.py
- Python script reverse_string.py produced >=2 lines of output
- crypto_signatures: no signatures found (informational)
- final_status.json validated

## Failed checks
- formal_verification: F_AGENTFIX FAIL (confidence=0.00)

## Artifact hashes
- `reverse_string.py`: `240d1dfc7394a2ec0e53f1581bc80fc466d24794deb726e0d08b1b313b2139e3`