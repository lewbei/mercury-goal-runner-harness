# Final Status: NOT_DONE

Run ID: `vs008_vertical_smoke`

## Authority
- final_status_authority: certifier_only
- can_certify_done: false
Status source: `certification.json`
Policy decision path: ``
Certification path: `certification.json`
Generated at: 2026-05-09T12:22:58.249446+00:00

## Passed checks
- goal_contract.json exists
- goal_contract.json parses as JSON
- trace.jsonl exists
- trace.jsonl lines parse as JSON
- step_logs contain at least one step result
- 001.json evidence maps to touched files
- done_criteria is non-empty
- final_outputs is non-empty
- final output exists: output.txt
- final_status.json validated

## Failed checks
- replay_check: REPLAY_MISMATCH blocks certification
-   replay check failed: certification_exists: certification.json missing
-   replay check failed: policy_decision_exists: policy_decision.json missing
-   replay check failed: policy_cert_match: Cannot compare: certification or policy missing
-   replay check failed: final_status_exists: final_status.json missing
-   replay check failed: final_status_cert_match: Cannot compare: final_status or certification missing

## Artifact hashes
- `output.txt`: `ff790e9e44f76f023d8d2c14df5656811e4372a56854fba24d7072a6088c11b1`