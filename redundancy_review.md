# Redundancy Review

Owner: Mercury Goal Runner Harness
Status: active-supporting
Last verified: 2026-05-07

## Review Result

The workspace is clean enough to proceed with the verifier-provenance direction, but there is intentional overlap between implementation-status docs and research-direction docs.

## File Groups

| Layer | Source of truth | Supporting files | Status |
|---|---|---|---|
| Repository overview | `README.md` | `PROJECT_STATUS.md` | Current |
| Implementation status | `PROJECT_STATUS.md` | `FRAMEWORK.md`, `docs/V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md` | Current |
| Research gap | `PROBLEM_AND_GAP.md` | `VERIFIER_PROVENANCE_DESIGN.md` | Current |
| Verifier provenance design | `VERIFIER_PROVENANCE_DESIGN.md` | `certification_policy.yaml` | Current |
| Provenance diagnostic evidence | `.agentic-pi/diagnostics/provenance_gate/diagnostic_report.md` | `docs/V0_3_3_PROVENANCE_GATE_DIAGNOSTICS.md`, `tests/test_provenance_gate.py` | Current |
| Smell scanner evidence | `docs/V0_3_4_SMELL_SCANNER.md` | `.agentic-pi/validators/smell_scanner.py`, `tests/test_smell_scanner.py` | Current |
| Strength scorer evidence | `docs/V0_3_5_STRENGTH_SCORER.md` | `.agentic-pi/validators/strength_scorer.py`, `tests/test_strength_scorer.py` | Current |
| Policy and certification evidence | `docs/V0_3_6_POLICY_ENGINE.md` | `.agentic-pi/runtime/policy_engine.py`, `.agentic-pi/validators/certify_run.py`, `tests/test_policy_engine.py` | Current |
| Drift-aware replanning evidence | `docs/V1_5_DRIFT_AWARE_REPLANNING.md` | `.agentic-pi/runtime/drift_detector.py`, `.agentic-pi/runtime/drift_proof_runner.py`, `tests/test_drift_replanning.py` | Current |
| Trajectory-level evaluation evidence | `docs/V1_6_TRAJECTORY_LEVEL_EVALUATION.md` | `.agentic-pi/evaluation/`, `.agentic-pi/diagnostics/trajectory_evaluation/`, `tests/test_trajectory_evaluation.py` | Current |
| Experience memory evidence | `docs/V1_7_EXPERIENCE_MEMORY.md` | `.agentic-pi/runtime/experience_extractor.py`, `.agentic-pi/runtime/experience_retriever.py`, `tests/test_experience_memory.py` | Current |
| Domain pack evidence | `docs/V1_8_DOMAIN_PACKS.md` | `.agentic-pi/domain_packs/`, `.agentic-pi/runtime/domain_pack_selector.py`, `tests/test_domain_packs.py` | Current |
| Navigation | `workspace_index.md` | this file | Current |

## Outdated Or Superseded Direction

The previous immediate milestone was domain packs after experience memory. That is now implemented.

The active next step is v1.9 Strategy Search / Workflow Optimization. Strategy search must stay advisory to execution planning and cannot certify DONE.

## Remaining Risk

The current code still uses `DONE_PASS` / `DONE_FAIL` for legacy runs, while provenance-mode runs with `verifier_contract.json` can return `NOT_DONE`, `PROVISIONAL_DONE`, or `CERTIFIED_DONE`. That split is intentional compatibility behavior, not a doc conflict.

The current diagnostic set covers only four deterministic provenance-gate cases. It is evidence for the first gate, not evidence for full oracle governance.

The current smell scanner records metadata-level smell reports. They are consumed downstream by strength scoring and policy decisions.

The current trajectory evaluator records and scores tool-use behavior. It is evidence for trajectory discipline, not evidence that the final artifact is semantically correct.

The current experience memory stores reusable strategy lessons. It is evidence for advisory strategy scoring, not evidence that memory can certify or bypass policy.

The current domain-pack layer stores deterministic task-domain hints. It is evidence for domain-aware strategy generation, not evidence that domain packs are semantically optimal or can certify DONE.

## Decision

Do not archive v0.2.1 or v0.3 docs. They describe implemented layers. Keep them as active supporting files, with `PROBLEM_AND_GAP.md` and `VERIFIER_PROVENANCE_DESIGN.md` as the current research-direction sources of truth.
