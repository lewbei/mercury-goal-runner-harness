# Final Status: NOT_DONE

Run ID: `qrspi_final`

## Authority
- final_status_authority: certifier_only
- can_certify_done: false
Status source: `policy_decision.json`
Policy decision path: `policy_decision.json`
Certification path: `certification.json`
Generated at: 2026-05-10T04:33:46.153165+00:00

## Passed checks
- verifier_contract.json exists
- verifier_contract.json parses as JSON
- goal_contract.json exists
- goal_contract.json parses as JSON
- policy_decision.json validates
- policy engine status: NOT_DONE
- final_status.json validated

## Failed checks
- verifier_contract.json schema validation failed: $: missing required field 'run_id'
- verifier_contract.json schema validation failed: $: missing required field 'target_goal'
- verifier_contract.json schema validation failed: $: missing required field 'target_artifacts'
- verifier_contract.json schema validation failed: $: missing required field 'required_verifier_level'
- verifier_contract.json schema validation failed: $: missing required field 'allow_self_generated_only'
- verifier_contract.json schema validation failed: $: missing required field 'required_behaviors'
- verifier_contract.json schema validation failed: $: missing required field 'forbidden_verifier_patterns'
- verifier_contract.json schema validation failed: $: missing required field 'minimum_strength_level'
- verifier_contract.json schema validation failed: $: missing required field 'certifying_authority_levels'
- verifier_contract.json schema validation failed: $: missing required field 'provisional_authority_levels'
- verifier_contract.json schema validation failed: $: unexpected field 'requirements'
- trace.jsonl missing
- step_logs directory missing
- done_criteria is empty
- final_outputs is empty
- evidence_index.json invalid: evidence_index.json missing required evidence kinds: ['STEP_LOG', 'TRACE']

## Artifact hashes
- none