# Final Status: DONE_FAIL

Run ID: `iter_test2`

## Authority
- final_status_authority: certifier_only
- can_certify_done: false
Status source: `certification.json`
Policy decision path: ``
Certification path: `certification.json`
Generated at: 2026-05-10T08:23:44.219611+00:00

## Passed checks
- goal_contract.json exists
- goal_contract.json parses as JSON
- trace.jsonl exists
- trace.jsonl lines parse as JSON
- step_logs contain at least one step result
- 1.json evidence maps to touched files
- done_criteria is non-empty
- final_outputs is non-empty
- final output exists: longest_palindrome.py
- Python module longest_palindrome.py imports cleanly
- formal_verification: F_ITER_TEST2 PASS (confidence=1.00)
- crypto_signature: longest_palindrome.py AUTHENTIC
- final_status.json validated

## Failed checks
- PlanGraph validation failed
- PlanGraph: plan_graph.json schema validation failed: $.edges[0].type: value 'flow' not in enum ['produces', 'requires']
- PlanGraph: plan_graph.json schema validation failed: $.edges[1].type: value 'output' not in enum ['produces', 'requires']
- PlanGraph: task node n1 must have matching task_id
- PlanGraph: edge source missing from graph nodes: START
- PlanGraph: edge target missing from graph nodes: END
- PlanGraph: task_graph missing task IDs: ['n1']
- PlanGraph: task_graph has unknown task IDs: ['step1']

## Artifact hashes
- `longest_palindrome.py`: `65a1f7de36ffa1c438ff1328b8abd8c665da507c811d1cd8b60753ec33068343`