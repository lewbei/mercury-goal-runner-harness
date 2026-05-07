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
| Implementation status | `PROJECT_STATUS.md` | `docs/V0_2_1_FREEZE.md`, `docs/V0_3_PLANGRAPH.md` | Current |
| Research gap | `PROBLEM_AND_GAP.md` | `VERIFIER_PROVENANCE_DESIGN.md` | Current |
| Verifier provenance design | `VERIFIER_PROVENANCE_DESIGN.md` | `certification_policy.yaml` | Current |
| Provenance diagnostic evidence | `.agentic-pi/diagnostics/provenance_gate/diagnostic_report.md` | `docs/V0_3_3_PROVENANCE_GATE_DIAGNOSTICS.md`, `tests/test_provenance_gate.py` | Current |
| Navigation | `workspace_index.md` | this file | Current |

## Outdated Or Superseded Direction

The previous immediate milestone was evidence-seeking branch selection after PlanGraph. That is no longer the active next step.

Branch selection is deferred. The active next step is verifier provenance governance.

## Remaining Risk

The current code still uses `DONE_PASS` / `DONE_FAIL` for legacy runs, while provenance-mode runs with `verifier_contract.json` can return `NOT_DONE`, `PROVISIONAL_DONE`, or `CERTIFIED_DONE`. That split is intentional compatibility behavior, not a doc conflict.

The current diagnostic set covers only four deterministic provenance-gate cases. It is evidence for the first gate, not evidence for full oracle governance.

## Decision

Do not archive v0.2.1 or v0.3 docs. They describe implemented layers. Keep them as active supporting files, with `PROBLEM_AND_GAP.md` and `VERIFIER_PROVENANCE_DESIGN.md` as the current research-direction sources of truth.
