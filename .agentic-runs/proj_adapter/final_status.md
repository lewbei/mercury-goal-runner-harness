# Final Status: DONE_FAIL

Run ID: `proj_adapter`

## Authority
- final_status_authority: certifier_only
- can_certify_done: false
Status source: `certification.json`
Policy decision path: ``
Certification path: `certification.json`
Generated at: 2026-05-10T10:15:38.281436+00:00

## Passed checks
- goal_contract.json exists
- goal_contract.json parses as JSON
- trace.jsonl exists
- trace.jsonl lines parse as JSON
- step_logs contain at least one step result
- 1.json evidence maps to touched files
- done_criteria is non-empty
- final_outputs is non-empty
- formal_verification: no artifacts dir (informational)
- crypto_signatures: no signatures found (informational)
- final_status.json validated

## Failed checks
- 1.json touched file missing: .agentic-pi/runtime/project_adapter.py
- step 1 touched files do not include merged plan path: project_adapter.py
- PlanGraph validation failed
- PlanGraph: produced artifact missing at exact path: project_adapter.py -> project_adapter.py
- PlanGraph: artifact_registry validation.exists must be true for project_adapter.py
- final output missing: .agentic-pi/runtime/project_adapter.py

## Artifact hashes
- none