# v2.0 Examples

These examples are proof-package examples for the Verifier-Provenance Goal
Runner Harness. They are not claims of full autonomous Pi runtime.

## Legacy DONE_PASS

Reference:

```text
.agentic-pi/benchmark/goals/simple_goal.json
```

Legacy runs without `verifier_contract.json` can still emit:

```text
DONE_PASS
```

## PROVISIONAL_DONE

Reference:

```text
.agentic-pi/diagnostics/evaluation/cases/p1_visible_only
```

Expected policy-engine status:

```text
PROVISIONAL_DONE
```

## CERTIFIED_DONE

Reference:

```text
.agentic-pi/diagnostics/evaluation/cases/p2_strong
```

Expected policy-engine status:

```text
CERTIFIED_DONE
```

## NOT_DONE

Reference:

```text
.agentic-pi/diagnostics/evaluation/cases/missing_verifier
```

Expected policy-engine status:

```text
NOT_DONE
```

## Drift Detected

Reference:

```text
tests/test_drift_replanning.py
```

The drift layer can mark status-artifact writes and verifier-artifact writes as
fatal drift. Drift reports can block, but cannot certify DONE.

## Trajectory Failure

Reference:

```text
.agentic-pi/diagnostics/trajectory_evaluation/cases/manual_status_write.jsonl
```

Trajectory evaluation can fail unsafe tool use. It cannot certify DONE.

## Memory Suggestion

Reference:

```text
tests/test_experience_memory.py
```

Experience memory can adjust strategy score. It cannot bypass the applicability
gate and cannot certify DONE.

## Domain Pack Selection

Reference:

```text
tests/test_domain_packs.py
```

Domain packs can shape strategy candidates and verifier hints. They cannot
certify DONE.

## Workflow Search

workflow search records candidate ranking evidence only.

Reference:

```text
tests/test_workflow_search.py
```

Workflow search can reject certifier-bypass and high false-certified-risk
workflow candidates. It cannot execute the selected workflow and cannot certify
DONE.

## Proof Matrix

Quick proof command:

```cmd
python .agentic-pi\runtime\run_proof_matrix.py --mode quick
```

The proof matrix writes:

```text
.agentic-runs/proof_matrix_outputs/proof_matrix_result.json
```

Final status still comes only from:

```text
certify_run.py
policy_engine.py
```
