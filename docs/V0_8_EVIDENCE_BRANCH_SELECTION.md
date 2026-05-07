# v0.8 Evidence-Seeking Branch Selection

This document records the v0.8 evidence-seeking branch selection slice.

It selects candidate branches by their path to verifier-provenance
certification. It does not certify DONE.

## Status

```text
EVIDENCE-SEEKING BRANCH SELECTION IMPLEMENTED
```

## Rule

```text
Do not choose a branch by model preference alone.
Choose only branches that declare a path to P2/P3 certifying verifier evidence.
If no branch has that path, ask for stronger verifier evidence.
```

Final status still comes only from:

```text
certify_run.py
policy_engine.py
```

## Runtime

The selector is:

```text
.agentic-pi/runtime/evidence_branch_selector.py
```

It reads:

```text
branch_manifest.json
branches/<branch_id>/branch_candidate.json
```

It writes:

```text
branch_decision.json
selected_branch.json
rejected_branches.json
selector_audit.json
```

It never writes:

```text
final_status.md
certification.json
policy_decision.json
```

## Decisions

Possible selector decisions:

```text
SELECTED
NEED_USER_VERIFIER
NO_CERTIFIABLE_BRANCH
```

These are selector decisions, not certification statuses.

## Safe claim

Safe claim:

```text
The harness can select a candidate branch based on whether it has a path to
verifier-provenance certification, and fail closed when no branch has that path.
```

Unsafe claim:

```text
The selected branch is DONE.
```

That remains false until `certify_run.py` / `policy_engine.py` runs.

## Proof commands

```cmd
python tests\test_evidence_branch_selector.py -v
python -m unittest discover tests -v
python .agentic-pi\diagnostics\evaluation\run_diagnostic_evaluation.py
python .agentic-pi\benchmark\run_benchmark.py
```
