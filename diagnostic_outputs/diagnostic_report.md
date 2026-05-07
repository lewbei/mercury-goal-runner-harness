# v0.4 Diagnostic Evaluation Report

Generated on 2026-05-07T02:44:09.202247+00:00
Total cases: 6

## Case Matrix

| Case | Expected | File Exists | Artifact Test | Provenance Gate | Policy Engine |
|---|---|---|---|---|---|
| file_exists_but_wrong | not certified | CERTIFIED_DONE | NOT_DONE | NOT_DONE | NOT_DONE |
| missing_verifier | not certified | CERTIFIED_DONE | NOT_DONE | NOT_DONE | NOT_DONE |
| p1_visible_only | not certified | CERTIFIED_DONE | CERTIFIED_DONE | PROVISIONAL_DONE | PROVISIONAL_DONE |
| p2_strong | certified | CERTIFIED_DONE | CERTIFIED_DONE | CERTIFIED_DONE | CERTIFIED_DONE |
| p2_weak | not certified | CERTIFIED_DONE | CERTIFIED_DONE | CERTIFIED_DONE | PROVISIONAL_DONE |
| self_test_only | not certified | CERTIFIED_DONE | CERTIFIED_DONE | PROVISIONAL_DONE | PROVISIONAL_DONE |

## Metrics

| Mode | False CERTIFIED_DONE Rate | Precision | Provisional Rate | NOT_DONE Rate | False Block Rate | Status Match Rate |
|---|---:|---:|---:|---:|---:|---:|
| file_existence | 1.000 | 0.167 | 0.000 | 0.000 | 0.000 | 0.167 |
| artifact_test | 0.600 | 0.250 | 0.000 | 0.333 | 0.000 | 0.500 |
| provenance_gate | 0.200 | 0.500 | 0.333 | 0.333 | 0.000 | 0.833 |
| policy_engine | 0.000 | 1.000 | 0.500 | 0.333 | 0.000 | 1.000 |

## Claim Boundary

This is a small deterministic diagnostic evaluation. It does not claim broad benchmark validity, oracle quality, Pi integration, or real Mercury planner quality.
