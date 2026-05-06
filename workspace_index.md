# Workspace Index

Owner: Mercury Goal Runner Harness
Status: source-of-truth
Last verified: 2026-05-06

## Current Direction

The implemented local layer is v0.3.2 Provenance Runtime Gate on top of v0.3 Artifact-Linked PlanGraph. The research direction is Verifier-Provenance Goal Runner Harness, centered on:

```text
Who is allowed to certify DONE?
```

## Source-Of-Truth Files

- `README.md` - repository overview and current commands.
- `PROJECT_STATUS.md` - implementation status and limitations.
- `PROBLEM_AND_GAP.md` - current research problem and gap.
- `VERIFIER_PROVENANCE_DESIGN.md` - verifier authority model and deferred implementation boundary.
- `certification_policy.yaml` - draft static policy vocabulary for later policy-engine implementation.

## Active Supporting Files

- `docs/V0_2_1_FREEZE.md` - fake-DONE baseline boundary.
- `docs/V0_3_PLANGRAPH.md` - current PlanGraph prototype boundary.
- `PLAN_ROUTER.md` - deterministic planner stub note.

## Known Cleanup Debt

- The working tree contains uncommitted v0.3 PlanGraph changes plus the new verifier-provenance docs/schemas.
- The certifier still emits `DONE_PASS` / `DONE_FAIL` for legacy runs without `verifier_contract.json`.
- Provenance-mode runs can emit `NOT_DONE`, `PROVISIONAL_DONE`, or `CERTIFIED_DONE`.
- No diagnostic verifier-provenance benchmark should be added until the model and policy engine are locked.
