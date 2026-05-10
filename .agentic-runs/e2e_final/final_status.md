# Final Status: CERTIFIED_DONE

Run ID: `e2e_final`

## Authority
- final_status_authority: certifier_only
- can_certify_done: false
Status source: `policy_decision.json`
Policy decision path: `policy_decision.json`
Certification path: `certification.json`
Generated at: 2026-05-10T10:41:24.264822+00:00

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
- final output exists: count_vowels.py
- Python script count_vowels.py produced >=2 lines of output
- verifier target artifact exists: count_vowels.py
- verifier_artifacts contain 2 artifact(s)
- verifier smell scan recorded: F.E2E_FINAL
- verifier smell scan recorded: V.E2E_FINAL
- verifier strength score recorded: F.E2E_FINAL=gating
- verifier strength score recorded: V.E2E_FINAL=certifying
- policy_decision.json validates
- policy engine status: CERTIFIED_DONE
- evidence_index.json validates
- evidence_freeze.json validates
- formal_verification: F_E2E_FINAL PASS (confidence=0.50)
- crypto_signatures: no signatures found (informational)
- final_status.json validated

## Failed checks
- none

## Artifact hashes
- `count_vowels.py`: `575e95a87fa7af3cea41bf52a872c40d13555f4cd9b51710eaa1c02642710872`