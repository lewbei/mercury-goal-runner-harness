# Final Status: DONE_FAIL

Run ID: `qrspi_test`

## Authority
- final_status_authority: certifier_only
- can_certify_done: false
Status source: `certification.json`
Policy decision path: ``
Certification path: `certification.json`
Generated at: 2026-05-10T10:47:41.254690+00:00

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
- final output exists: is_perfect_square.py
- Python script is_perfect_square.py produced >=2 lines of output
- crypto_signatures: no signatures found (informational)
- final_status.json validated

## Failed checks
- formal_verification: F_QRSPI_TEST FAIL (confidence=0.67)

## Artifact hashes
- `is_perfect_square.py`: `df890bc67e2b31d6fa442aee843900370d812e3b87402da62e3f13997dc88ea1`