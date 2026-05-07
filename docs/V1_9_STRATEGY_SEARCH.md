# v1.9 Strategy Search / Workflow Optimization

```text
STRATEGY SEARCH IMPLEMENTED
```

v1.9 adds a deterministic workflow-candidate search layer. It is deliberately
small: it compares workflow candidates and writes a search trace. It does not
execute the selected workflow, run a worker, or certify DONE.

The invariant is unchanged:

```text
Strategy can suggest.
Planner can select.
Milestones can guide.
Memory can suggest.
Domain packs can suggest.
Workflow search can rank.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

workflow search cannot bypass certifier.

workflow search cannot certify DONE.

## Implemented Files

```text
.agentic-pi/runtime/workflow_search.py
.agentic-pi/schemas/workflow_candidate.schema.json
.agentic-pi/schemas/workflow_search_trace.schema.json
tests/test_workflow_search.py
```

## Runtime Path

```text
goal_contract.json
  -> optional task_type_decision.json
  -> optional domain_pack_selection.json
  -> optional retrieved_experience.json
  -> optional trajectory_score.json
  -> optional drift_report.json
  -> workflow_candidates.json
  -> selected_workflow.json
  -> workflow_search_trace.json
```

The search layer uses:

```text
trajectory score
false CERTIFIED_DONE risk
cost estimate
verifier strength path
drift history risk
domain-pack hint
experience-memory hint
```

It rejects workflows that:

```text
bypass certify_run.py / policy_engine.py
write final_status.md
write certification.json
write policy_decision.json
write verifier artifacts without authorization
hide failed checks
carry high false CERTIFIED_DONE risk
```

## Candidate Types

The deterministic candidate pool currently includes:

```text
W.FIXED_POLICY_PIPELINE
W.DOMAIN_MEMORY_POLICY
W.HIGH_FALSE_CERTIFIED_RISK
W.UNSAFE_BYPASS_CERTIFIER
```

The unsafe candidates are intentional negative cases. They prove that workflow
search has a rejection path and does not choose a workflow just because it is
cheap or short.

## Output

`workflow_search.py` writes:

```text
workflow_candidates.json
selected_workflow.json
workflow_search_trace.json
```

`workflow_search_trace.json` records:

```text
decision_status
selected_workflow
workflow_scores
rejected_workflows
selector_checks
final_status_authority = certifier_only
can_certify_done = false
```

## What v1.9 Proves

```text
workflow search selects a lower-risk certifier-preserving workflow
workflow trying to bypass the certifier is rejected
workflow with high false-certified risk is rejected
search trace records rejected reasons
fixed pipeline still exists as a safe candidate
workflow search does not write status artifacts
```

## What v1.9 Does Not Prove

```text
workflow search is globally optimal
MCTS or AFlow-style search is implemented
selected workflow execution is integrated
full autonomous Pi chain runtime is safe
semantic quality of workflow candidates
workflow search can certify final status
```

## Proof Commands

```cmd
python tests\test_workflow_search.py -v
python -m unittest discover tests -v
```

For Pi smoke:

```cmd
pi --tools bash -p "Run exactly one bash command: python tests/test_workflow_search.py -v. Do not certify DONE yourself. Final status comes only from certify_run.py."
```

## Next

Next milestone:

```text
v2.0 = Integrated Harness Proof Package
```

v2.0 should add a proof matrix and a one-command proof runner. It must keep
tested behavior separate from unverified behavior.
