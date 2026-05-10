# Final Status: NOT_DONE

Run ID: `build_pipeline`

## Authority
- final_status_authority: certifier_only
- can_certify_done: false
Status source: `policy_decision.json`
Policy decision path: `policy_decision.json`
Certification path: `certification.json`
Generated at: 2026-05-10T09:52:09.765775+00:00

## Passed checks
- verifier_contract.json exists
- verifier_contract.json parses as JSON
- goal_contract.json exists
- goal_contract.json parses as JSON
- trace.jsonl exists
- trace.jsonl lines parse as JSON
- step_logs contain at least one step result
- 1.json evidence maps to touched files
- done_criteria is non-empty
- final_outputs is non-empty
- verifier_artifacts contain 1 artifact(s)
- verifier smell scan recorded: V.BUILD_PIPELINE
- verifier strength score recorded: V.BUILD_PIPELINE=certifying
- policy_decision.json validates
- policy engine status: NOT_DONE
- evidence_index.json validates
- evidence_freeze.json validates
- formal_verification: no formal artifacts (informational)
- crypto_signatures: no signatures found (informational)
- final_status.json validated

## Failed checks
- 1.json touched file missing: .agentic-pi/runtime/orchestrate_pipeline.py
- PlanGraph validation failed
- PlanGraph: produced artifact missing at exact path: orchestrate_pipeline.py -> .agentic-pi/runtime/orchestrate_pipeline.py
- PlanGraph: artifact_registry validation.exists must be true for orchestrate_pipeline.py
- final output missing: orchestrate_pipeline.py
- Done criterion failed: orchestrate_pipeline.py exists in .agentic-pi/runtime/ (orchestrate_pipeline.py missing)
- verifier target artifact missing: .agentic-pi/runtime/orchestrate_pipeline.py

## Artifact hashes
- none