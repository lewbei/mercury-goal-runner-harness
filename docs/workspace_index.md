# Workspace Index

Owner: Mercury Goal Runner Harness
Status: source-of-truth
Last verified: 2026-05-08

## Current Direction

The implemented local layer is RPG-Harness v5 Phase 2-8 (Supervisor Ledger,
Artifact Routing, Success Criteria/Oracles, Validator Factory, Replay
Certification, Memory Split, Meta-Harness v0.1) on top of v3.7 MemPalace
+ ACE Memory Governance.
The research direction is Verifier-Provenance Goal Runner Harness,
centered on:

```text
Who is allowed to certify DONE?
```

## Source-Of-Truth Files

- `README.md` - repository overview and current commands.
- `PROJECT_STATUS.md` - implementation status and limitations.
- `FRAMEWORK.md` - conceptual architecture and actual current file map.
- `docs/V5_ARCHITECTURE_GUIDE.md` - corrected V5 architecture plan with per-layer build status (✅ exists / 🔧 needs work).
- `.agentic-pi/README.md` - local harness folder ownership map.
- `.agentic-pi/runtime/README.md` - runtime module ownership map.
- `.agentic-pi/diagnostics/README.md` - deterministic diagnostic fixture map.
- `PROBLEM_AND_GAP.md` - current research problem and gap.
- `VERIFIER_PROVENANCE_DESIGN.md` - verifier authority model and deferred implementation boundary.
- `docs/V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md` - completed v1.3-v2.1 roadmap.
- `docs/V2_7_AGENTIC_AUTONOMY_PROOF_PLAN.md` - real Pi/Mercury agentic autonomy probe boundary.
- `docs/V2_8_AGENTIC_NEGATIVE_PROBES.md` - arbitrary-chain and unbounded-bash negative-probe boundary.
- `docs/V2_9_LIVE_NEGATIVE_PROMPT_CAPTURE.md` - live negative prompt capture boundary.
- `docs/V3_0_REAL_PI_BEHAVIOR_EVALUATION.md` - real Pi behavior evaluation boundary.
- `docs/V3_1_REAL_PI_PROMPT_COVERAGE.md` - real Pi prompt coverage boundary.
- `docs/V3_2_RUNTIME_ENFORCEMENT_PROOF.md` - runtime enforcement proof boundary.
- `docs/RPG_HARNESS_TEST_FORM.md` - RPG test form and statistical test-record boundary.
- `docs/V3_4_RPG_TEST_AGGREGATION.md` - RPG test-record aggregation boundary.
- `docs/V3_5_0_AUTHORITY_ARTIFACT_PREREQUISITE.md` - v3.5.0 Authority Artifact Prerequisite: final_status.json machine-readable authority boundary.
- `docs/V3_5_EVIDENCE_FREEZE.md` - frozen producer-linked evidence boundary.
- `docs/V3_6_RUN_LOCAL_AND_QUARANTINE_MEMORY.md` - run-local and quarantine memory boundary.
- `docs/V3_7_MEMPALACE_ACE_MEMORY_GOVERNANCE.md` - structured advisory memory governance boundary.
- `docs/V3_5_TO_V4_0_AUTHORITY_EVIDENCE_MEMORY_PLAN.md` - implemented authority-artifact prerequisite plus evidence-freeze, ACE/MemPalace memory, context-board, adapter, and paper-evaluation roadmap.
- `certification_policy.yaml` - draft static policy vocabulary.

- `.agentic-pi/run_kernel/` - RPG-Harness v5 Phase 2 supervisor ledger: run kernel, transition validator, phase registry, work packet lifecycle, dispatch ledger, protected core artifacts.
- `.agentic-pi/core/` - RPG-Harness v5 trusted core: core authority policy, protected artifacts, status lattice, trusted core manifest.
- `.agentic-pi/artifacts/` - RPG-Harness v5 Phase 3 artifact routing: expected_artifacts schema, artifact contract schema, placement policy, location/misplacement/fallback/satisfaction validators.
- `tests/test_supervisor_ledger.py` - 57 deterministic tests for transition validation, run kernel state machine, work packet lifecycle, dependencies, trusted core files, and integration scenarios.
- `tests/test_artifact_routing.py` - 46 deterministic tests for artifact schema validation, location checking, misplacement detection, fallback detection, content satisfaction, and kernel integration.

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
- `docs/V2_7_AGENTIC_AUTONOMY_PROOF_PLAN.md` - implemented real agentic autonomy probe boundary.
- `docs/V2_8_AGENTIC_NEGATIVE_PROBES.md` - implemented agentic negative-probe hardening boundary.
- `docs/V2_9_LIVE_NEGATIVE_PROMPT_CAPTURE.md` - implemented negative prompt capture boundary.
- `docs/V3_0_REAL_PI_BEHAVIOR_EVALUATION.md` - implemented real Pi behavior evaluation boundary.
- `docs/V3_1_REAL_PI_PROMPT_COVERAGE.md` - implemented real Pi prompt coverage boundary.
- `docs/V3_2_RUNTIME_ENFORCEMENT_PROOF.md` - implemented runtime enforcement proof boundary.
- `docs/RPG_HARNESS_TEST_FORM.md` - implemented RPG test-record boundary.
- `docs/V3_4_RPG_TEST_AGGREGATION.md` - implemented RPG test aggregation boundary.
- `.agentic-pi/diagnostics/provenance_gate/` - four-case copy-ready provenance diagnostic set.
- `.agentic-pi/diagnostics/trajectory_evaluation/` - six-case trajectory-level diagnostic set.
- `.agentic-pi/prompts/agentic_autonomy_probe.md` - paste-ready real Pi probe prompt.
- `.agentic-pi/prompts/negative_autonomy/` - paste-ready negative Pi/Mercury prompt templates.
- `.agentic-pi/prompts/real_behavior_matrix/` - bounded real Pi/Mercury prompt coverage templates.
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
- The v2.7 autonomy probe is a monitored live Pi/Mercury experiment on a disposable run. It proves a bounded chain read, advisory memory read, one repair loop, and certifier-only final authority; it does not prove arbitrary chain following or unbounded bash is safe.
- The v2.8 negative probes harden that boundary for unapproved chain reads, source-tree write commands, and second repair commands; they do not prove every possible unsafe command string is classified.
- The v2.9 negative prompt capture path passes only when the monitor observes and rejects the expected unsafe prompt behavior; it does not prove every malicious prompt is classified.
- The v3.0 real Pi behavior evaluation classifies captured behavior as unsafe caught, unsafe missed, safe refusal, or inconclusive; it does not prove broad prompt coverage.
- The v3.1 real Pi prompt coverage matrix covers ten bounded negative prompt categories with repeated-trial support; it does not prove arbitrary prompt coverage or arbitrary unbounded bash safety.
- The v3.3 RPG test record turns a smoke or adversarial run into a schema-valid evidence record with expected failure mode, catch layer, regression decision, and statistical inclusion. It cannot certify DONE.
- The v3.4 RPG aggregation layer reports false-certified, monitor-miss, false-block, and confidence-interval metrics over collected records only. It cannot certify DONE or prove arbitrary prompt coverage.
- The v3.5.0 authority artifact layer makes `final_status.json` machine-readable authority and keeps `final_status.md` derived. It cannot certify DONE beyond `certify_run.py` / `policy_engine.py`.
- The v3.5.1 evidence-freeze layer indexes and freezes producer-linked evidence while excluding memory paths.
- The v3.6 run-local/quarantine memory layer can record observations and candidate lessons, but memory remains advisory, non-durable, excluded from evidence, and unable to certify DONE.
- The v3.7 MemPalace/ACE layer can store durable advisory cards, build bounded context packs, reflect helpful/harmful memory use, and promote cards only through `memory_write_gate.py`; it still cannot certify DONE or replace evidence.
- The `modules/ace-main/` and `modules/mempalace-develop/` folders are local ignored references only. They informed v3.7 memory governance design, but they are not vendored harness dependencies.
