# Final Status: DONE_FAIL

Run ID: `repairtest`

## Authority
- final_status_authority: certifier_only
- can_certify_done: false
Status source: `certification.json`
Policy decision path: ``
Certification path: `certification.json`
Generated at: 2026-05-10T10:31:45.791877+00:00

## Passed checks
- goal_contract.json exists
- goal_contract.json parses as JSON
- step_logs contain at least one step result
- done_criteria is non-empty
- final_outputs is non-empty
- final output exists: hello.py
- formal_verification: no artifacts dir (informational)
- crypto_signatures: no signatures found (informational)
- final_status.json validated

## Failed checks
- trace.jsonl missing
- 1.json field files_touched has wrong type: expected list
- 1.json files_touched must contain at least one path
- Python script hello.py exit=0, lines=1

## Artifact hashes
- `hello.py`: `b80792336156c7b0f7fe02eeef24610d2d52a10d1810397744471d1dc5738180`