# Final Status: DONE_PASS

Run ID: `swetest_m`

## Authority
- final_status_authority: certifier_only
- can_certify_done: false
Status source: `certification.json`
Policy decision path: ``
Certification path: `certification.json`
Generated at: 2026-05-10T05:52:23.719409+00:00

## Passed checks
- goal_contract.json exists
- goal_contract.json parses as JSON
- trace.jsonl exists
- trace.jsonl lines parse as JSON
- step_logs contain at least one step result
- 1.json evidence maps to touched files
- artifact_tests present
- artifact_test CLI_SUMMARY_TEST passed
- done_criteria is non-empty
- final_outputs is non-empty
- final output exists: cli_tool.py
- Done criterion delegated to artifact_tests: When run with a sample CSV, it prints at least two lines of summary.
- final_status.json validated

## Failed checks
- none

## Artifact hashes
- `cli_tool.py`: `2bedcd712a7e835842806d127dcc9262d37935bcb9537a548a0224babeb44f4b`