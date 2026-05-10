# Final Status: NOT_DONE

Run ID: `full_demo`

## Authority
- final_status_authority: certifier_only
- can_certify_done: false
Status source: `policy_decision.json`
Policy decision path: `policy_decision.json`
Certification path: `certification.json`
Generated at: 2026-05-10T08:29:28.802596+00:00

## Passed checks
- verifier_contract.json exists
- verifier_contract.json parses as JSON
- goal_contract.json exists
- goal_contract.json parses as JSON
- trace.jsonl exists
- trace.jsonl lines parse as JSON
- step_logs contain at least one step result
- 1.json evidence maps to touched files
- 2.json evidence maps to touched files
- done_criteria is non-empty
- final_outputs is non-empty
- final output exists: roman_to_int.py
- Python module roman_to_int.py imports cleanly
- verifier target artifact exists: roman_to_int.py
- verifier_artifacts contain 1 artifact(s)
- verifier smell scan recorded: F.FULL_DEMO
- verifier strength score recorded: F.FULL_DEMO=gating
- policy_decision.json validates
- policy engine status: NOT_DONE
- evidence_index.json validates
- evidence_freeze.json validates
- formal_verification: F_FULL_DEMO PASS (confidence=0.50)
- crypto_signature: roman_to_int.py AUTHENTIC
- final_status.json validated

## Failed checks
- 2.json touched file missing: test_roman_to_int.py
- step 1 action mismatch: expected write, got create_file
- PlanGraph validation failed

## Artifact hashes
- `roman_to_int.py`: `8e3e86000948add452380a1adf1aae7ca335bfee6409e83bfc50cb76a08c0636`