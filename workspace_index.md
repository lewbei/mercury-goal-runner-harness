# Workspace Index

Owner: Mercury Goal Runner Harness
Status: source-of-truth
Last verified: 2026-05-07

## Current Direction

The implemented local layer is v2.6 Real Pi Session Trace Capture on top of the
verifier-provenance certification stack. The next planned layer is v2.7 Real
Agentic Autonomy Proof Plan. The research direction is Verifier-Provenance Goal
Runner Harness, centered on:

```text
Who is allowed to certify DONE?
```

## Source-Of-Truth Files

- `README.md` - repository overview and current commands.
- `PROJECT_STATUS.md` - implementation status and limitations.
- `FRAMEWORK.md` - conceptual architecture and actual current file map.
- `.agentic-pi/README.md` - local harness folder ownership map.
- `.agentic-pi/runtime/README.md` - runtime module ownership map.
- `.agentic-pi/diagnostics/README.md` - deterministic diagnostic fixture map.
- `PROBLEM_AND_GAP.md` - current research problem and gap.
- `VERIFIER_PROVENANCE_DESIGN.md` - verifier authority model and deferred implementation boundary.
- `docs/V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md` - completed v1.3-v2.1 roadmap.
- `docs/V2_7_AGENTIC_AUTONOMY_PROOF_PLAN.md` - next proof plan for multi-step Pi/Mercury autonomy.
- `certification_policy.yaml` - draft static policy vocabulary.

## Active Supporting Files

- `docs/V0_2_1_FREEZE.md` - fake-DONE baseline boundary.
- `docs/V0_3_PLANGRAPH.md` - current PlanGraph prototype boundary.
- `docs/V0_3_2_PROVENANCE_GATE_FREEZE.md` - current provenance runtime gate boundary.
- `docs/V0_3_3_PROVENANCE_GATE_DIAGNOSTICS.md` - copy-ready provenance diagnostic fixture boundary.
- `docs/V0_3_4_SMELL_SCANNER.md` - metadata-level verifier smell scanner boundary.
- `docs/V0_3_5_STRENGTH_SCORER.md` - verifier strength scoring boundary.
- `docs/V0_3_6_POLICY_ENGINE.md` - deterministic policy engine boundary.
- `docs/V0_4_DIAGNOSTIC_EVALUATION.md` - small diagnostic evaluation boundary.
- `docs/V0_5_9_PI_COMMAND_DISCIPLINE_GATE.md` - deterministic Pi command-discipline audit boundary.
- `docs/V0_6_LOCAL_CODING_AGENT_HOST_INTEGRATION.md` - local host-task certification boundary.
- `docs/V0_9_REPLAY_ROLLBACK_AUDIT.md` - replay, rollback, and audit boundary.
- `docs/V1_0_PRACTICAL_PACKAGE_FREEZE.md` - thin local command surface boundary.
- `docs/V1_1_RAW_GOAL_CHAIN_PROOF.md` - deterministic raw-goal chain proof.
- `docs/V1_2_PLANNING_PROOF_HARDENING.md` - deterministic planning handoff proof.
- `docs/V1_3_STRATEGY_PLANNER.md` - deterministic strategy planner proof.
- `docs/V1_4_MILESTONE_PLANNING.md` - deterministic milestone planning proof.
- `docs/V1_5_DRIFT_AWARE_REPLANNING.md` - deterministic drift-aware replanning proof.
- `docs/V1_6_TRAJECTORY_LEVEL_EVALUATION.md` - deterministic trajectory-level evaluation proof.
- `docs/V1_7_EXPERIENCE_MEMORY.md` - advisory experience-memory proof.
- `docs/V1_8_DOMAIN_PACKS.md` - deterministic domain-pack proof.
- `docs/V1_9_STRATEGY_SEARCH.md` - deterministic workflow-search proof.
- `docs/V2_0_INTEGRATED_HARNESS_PROOF_PACKAGE.md` - integrated proof-matrix package.
- `docs/V2_0_EXAMPLES.md` - v2.0 example set.
- `docs/V2_1_CONTROLLED_PI_CHAIN_RUNTIME_PROOF.md` - controlled Pi chain runtime proof.
- `docs/V2_2_DIRECT_PI_MERCURY_BEHAVIOR_AUDIT.md` - direct Pi/Mercury behavior audit proof.
- `docs/V2_3_REAL_PI_INTERACTIVE_SMOKE.md` - real Pi interactive smoke evidence boundary.
- `docs/V2_4_REAL_PI_RUN_MONITOR.md` - captured real Pi run monitor boundary.
- `docs/V2_5_REAL_PI_NEGATIVE_STATUS_SMOKE.md` - negative-status Pi monitor boundary.
- `docs/V2_6_REAL_PI_SESSION_TRACE_CAPTURE.md` - real Pi session trace capture boundary.
- `docs/V2_7_AGENTIC_AUTONOMY_PROOF_PLAN.md` - planned real agentic autonomy proof boundary.
- `.agentic-pi/diagnostics/provenance_gate/` - four-case copy-ready provenance diagnostic set.
- `.agentic-pi/diagnostics/trajectory_evaluation/` - six-case trajectory-level diagnostic set.
- `.agentic-pi/prompts/agentic_autonomy_probe.md` - paste-ready real Pi probe prompt.
- `PLAN_ROUTER.md` - deterministic planner stub note.

## Known Cleanup Debt

- The certifier still emits `DONE_PASS` / `DONE_FAIL` for legacy runs without `verifier_contract.json`.
- Provenance-mode runs can emit `NOT_DONE`, `PROVISIONAL_DONE`, or `CERTIFIED_DONE`.
- The current provenance diagnostic set is intentionally four deterministic cases, not a broad benchmark.
- The trajectory diagnostic set is intentionally six deterministic session fixtures, not a proof of full autonomous Pi runtime.
- The policy engine consumes verifier provenance, smell reports, strength reports, and verifier contracts.
- Drift reports can block certification; trajectory evaluators can fail unsafe behavior. Neither can certify DONE.
- Experience memory can adjust strategy scores but cannot bypass applicability gates or certify DONE.
- Domain packs can shape strategy candidates and verifier hints, but cannot certify DONE.
- Workflow search can rank candidates and reject unsafe workflows, but cannot execute them or certify DONE.
- The proof matrix can report bounded proof command results, but cannot certify DONE.
- The controlled Pi chain smoke can report bounded Pi-process evidence, but cannot certify DONE or prove arbitrary Pi autonomy.
- Real Pi trace capture can monitor JSON event streams, but cannot prove arbitrary Pi autonomy by itself.
- The v2.7 autonomy probe is a planned monitored experiment. It should treat multi-step planning, repair, memory use, arbitrary chain following, and unbounded bash as behavior to audit, not as safety already proven.
