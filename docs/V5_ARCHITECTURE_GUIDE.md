# RPG-Harness v5 Architecture Guide

> Corrected cross-reference of the V5 architecture plan against the live repo.
> ✅ = exists, 🔧 = needs work, — = omitted from plan but exists in repo

## System Identity

```
RPG-Harness v5:
A rooted system-design planner and evidence-gated certification harness.

It decomposes a raw goal into phased artifacts, dispatches each task as a
bounded work packet to fresh-context agents, validates outputs against
artifact contracts and success criteria, certifies generated validators
before trusting them, freezes evidence, gates status through policy and
replay, and writes only advisory durable memory after final status is locked.
```

It is:

```
planner
+ supervisor controller
+ validator factory
+ certification harness
+ memory system
```

---

## Current implemented state

The repo is **not** at v3.1. It is at:

```
RPG-Harness v5 Phases 1-9
(Supervisor Ledger, Artifact Routing, Success Criteria/Oracles,
 Validator Factory, Replay Certification, Memory Split,
 Meta-Harness v0.1, QRSPI Skills)
on top of v3.7 MemPalace + ACE Memory Governance.
```

**PROJECT_STATUS.md** is the source of truth for version. The `workspace_index.md`
cross-references it. Keep these in sync — the plan should not lag behind.

Current local cleanup note: default runtime scripts are being strictified to fail closed. `full_verify.py` requires existing planning search/coverage artifacts, proof artifacts, and verifier evidence, and validates adaptive research inputs when present; `adaptive_research_inputs.py` records non-deterministic/autoresearch findings as optional planning-only provenance; `plan_router.py` requires existing planner-owned `plans/*_plan.json`; `plan_merger.py` writes `merged_plan.json` from `selected_plan.json`; and workers must not create fallback artifacts.

---

## The full architecture — annotated with current status

```
RPG-Harness v5
│
├──  0. Trusted Core Layer              ✅  core/
├──  1. Run Kernel / State Machine      ✅  run_kernel/
├──  2. Supervisor Ledger Layer         ✅  run_kernel/ + .agentic-runs/<id>/
├──  3. QRSPI Phase Layer               ✅  phase_registry.json
├──  4. Project Adapter Layer           🔧  project_adapters/ (envisioned)
├──  5. Success Criteria + Oracle       ✅  success/ + oracles/
├──  6. Artifact Contract / Routing     ✅  artifacts/
├──  7. Work Packet Dispatch Layer      ✅  run_kernel/work_packet.schema.json
├──  8. Role-Bounded Agent Layer        ✅  phase_registry.json roles
├──  9. Validator Factory Layer         ✅  validator_factory/
├── 10. Controlled Execution Layer      ✅  execution/ (validators: command_allowlist, write_scope, protected_files)
├── 11. Evidence Graph Layer            ✅  evidence_indexer.py + freezer
├── 12. Policy / Replay / Certify       ✅  policy_engine.py + replay/ + certifier
├── 13. Repair / Escalation Layer       ✅  repair/ (validators: repair_scope, repair_budget; schema: repair_packet)
├── 14. Memory Layer                    ✅  memory/
├── 15. Meta-Harness Evaluation Layer   ✅  diagnostics/meta_harness/ + proof_matrix/
├── 16. Skills Layer                    ✅  skills/ (12 skill directories)
│
└── —  Security Layer                   ✅  security/ (omitted from plan)
```

**Layers already built:** 0-3, 5-14, 16 + security
**Genuinely new layers needed:** 4 (project adapters — deferred)

---

## Layer-by-layer status

### 0. Trusted Core Layer ✅

Files exist:

```
.agentic-pi/core/
├── trusted_core_manifest.json          ✅
├── core_authority_policy.json          ✅
├── protected_artifacts.json            ✅
├── status_lattice.json                 ✅
└── validators/                         ✅ (.gitkeep)
```

**Correction to plan:** This layer is already formalized. No "now formalize"
step is needed. The plan's §3 accurately describes the contents but
incorrectly presents it as future work.

---

### 1. Run Kernel / State Machine Layer ✅

All states from the plan exist in `phase_registry.json`:

| Category | Plan lists | Registry has | Match |
|---|---|---|---|
| Normal | 18 states | 18 states | ✅ |
| Blocked | 8 states | 8 states | ✅ |
| Repair | 5 states | 5 states | ✅ |

All 37 transitions exist in `transition_rules.json`:

```
NEW -> INTAKE -> QUESTIONING -> RESEARCHING -> DESIGNING -> STRUCTURING
-> PLANNING -> WORKTREE_READY -> IMPLEMENTING -> VALIDATOR_BUILDING
-> VALIDATING -> EVIDENCE_INDEXING -> POLICY_DECIDING -> REPLAYING
-> CERTIFYING -> REPORTING -> MEMORY_CONSOLIDATING -> DONE

REPORTING -> DONE   (skip memory — allowed but plan omits it)

BLOCKED states -> respective REPAIRING states
BLOCKED_BY_AUTHORITY_VIOLATION -> REPAIRING_PLAN  (repairable, not terminal)
```

**Correction to plan:**
1. `REPORTING -> DONE` is a valid path that skips memory. The plan's flow
   diagram implies memory always runs.
2. `BLOCKED_BY_AUTHORITY_VIOLATION -> REPAIRING_PLAN` means authority
   violations are recoverable, not terminal.

Files:

```
.agentic-pi/run_kernel/
├── run_state.schema.json               ✅
├── transition_rules.json               ✅
├── validate_transition.py              ✅
├── phase_registry.json                 ✅
├── phase_budget.json                   ✅
├── phase_queue.schema.json             ✅
├── work_packet.schema.json             ✅
└── run_kernel.py                       ✅
```

---

### 2. Supervisor Ledger Layer ✅

The run folder structure already exists:

```
.agentic-runs/<run_id>/
├── run_state.json                      ✅
├── phase_queue.json                    ✅
├── dispatch_log.jsonl                  ✅
├── work_packets/                       (used by kernel)
├── validation_results/                 (used by kernel)
├── artifact_registry.json              ✅ (written by artifact_linker)
└── run_manifest.json                   ✅
```

Work packet statuses match the plan: PENDING, DISPATCHED, RESULT_RECEIVED,
VALIDATING, ACCEPTED, REJECTED, REPAIR_REQUESTED, REPAIRING, BLOCKED,
CANCELLED.

The supervisor loop described in the plan matches what `run_kernel.py`
already implements: read state → read queue → select → dispatch →
receive → validate → mark → repair if needed.

---

### 3. QRSPI Phase Layer ✅

The phase registry already maps each phase to its output artifact:

```
Question       -> question_contract.json        ✅
Research       -> research_pack.md              ✅
Design         -> design_options.json           ✅
Structure      -> structure_outline.json        ✅
Plan           -> plan_graph.json               ✅
Worktree       -> workspace_manifest.json       ✅
Implement      -> artifacts + trace logs         ✅
Verify         -> verifier_artifacts/            ✅
Policy         -> policy_decision.json           ✅
Replay         -> replay_report.json             ✅
Certify        -> certification.json + final_status.json  ✅
Report         -> pi_report.md                   ✅
Memory         -> memory_write_proposal.json     ✅
```

---

### 4. Project Adapter Layer 🔧 (new work)

Does not exist yet. The plan describes:

```
.agentic-pi/project_adapters/
├── project_profile.schema.json          🔧
├── adapter_registry.json               🔧
├── generated_adapter_proposals/        🔧
├── approved_adapters/                  🔧
└── validators/
    ├── validate_project_profile.py     🔧
    ├── validate_adapter_scope.py       🔧
    └── validate_adapter_authority.py   🔧
```

Suggestion: defer this layer until execution/ and repair/ are built.
The harness works today without project adapters.

---

### 5. Success Criteria + Oracle Layer ✅

Already implemented:

```
.agentic-pi/success/
├── success_criteria.schema.json                ✅
├── success_criteria_set.schema.json            ✅
├── success_criteria_compiler.py                ✅
└── validators/
    ├── validate_success_criteria.py            ✅
    ├── validate_success_measurability.py       ✅
    └── validate_success_to_oracle_mapping.py   ✅

.agentic-pi/oracles/
├── oracle_registry.json                        ✅
├── oracle_strength_rules.json                  ✅
└── validators/
    ├── validate_oracle_type.py                 ✅
    └── validate_oracle_strength.py             ✅
```

Oracle types in registry match the plan: STRUCTURAL_ORACLE, BEHAVIORAL_ORACLE,
SEMANTIC_ORACLE, COMPARATIVE_ORACLE, NEGATIVE_ORACLE, REPLAY_ORACLE,
EXTERNAL_ORACLE.

---

### 6. Artifact Contract / Routing Layer ✅

Already implemented:

```
.agentic-pi/artifacts/
├── expected_artifacts.schema.json              ✅
├── artifact_contract.schema.json               ✅
├── artifact_placement_policy.json              ✅
└── validators/
    ├── validate_expected_artifacts.py          ✅
    ├── validate_artifact_location.py           ✅
    ├── validate_no_fallback_artifacts.py       ✅
    └── validate_artifact_satisfaction.py       ✅
```

---

### 7. Work Packet Dispatch Layer ✅

work_packet.schema.json already exists in `run_kernel/`. The dispatch
ledger (`dispatch_log.jsonl`) is written by `run_kernel.py`.

---

### 8. Role-Bounded Agent Layer ✅

Phase registry assigns roles that match the plan:

| Plan role | Registry role |
|---|---|
| Supervisor Controller | (deterministic — not in phase registry) |
| Questioner | Questioner |
| Researcher | Researcher |
| Designer | Designer |
| Structurer | Structurer |
| Planner | Planner |
| Engineer | Engineer |
| Validator Designer / Engineer | ValidatorEngineer |
| Critic | Critic |
| Reporter | Reporter |
| Policy Judge | PolicyJudge |
| Replay Judge | ReplayJudge |
| Certifier | Certifier |
| Memory Clerk / Writer | MemoryWriter |

---

### 9. Validator Factory Layer ✅

Already implemented:

```
.agentic-pi/validator_factory/
├── validator_spec.schema.json                  ✅
├── validator_registry.json                     ✅
├── validator_authority_policy.json             ✅
├── fixture_suite.schema.json                   ✅
├── mutation_policy.json                        ✅
└── runtime/
    ├── run_validator_meta_check.py             ✅
    ├── run_validator_fixtures.py               ✅
    ├── run_validator_mutations.py              ✅
    └── certify_generated_validator.py          ✅
```

Validator authority levels match the plan: V0_PROPOSED, V1_LOCAL_TESTED,
V2_INDEPENDENT_TESTED, V3_EXTERNAL_TRUSTED, V4_CORE_TRUSTED.

---

### 10. Controlled Execution Layer 🔧 (new work)

Does not exist as a dedicated directory. The only related file is
`.agentic-pi/security/command_policy.json`.

The plan describes:

```
.agentic-pi/execution/
├── command_policy.json                 🔧  (partially in security/)
├── write_scope_policy.json             🔧
├── network_policy.json                 🔧
├── tool_registry.json                  🔧
└── validators/
    ├── validate_command_allowlist.py   🔧
    ├── validate_write_scope.py         🔧
    └── validate_protected_files.py     🔧
```

**Correction to plan:** The plan's §13 file list lives under `execution/`
but the existing `command_policy.json` lives under `security/`. Decide
whether to:
- Move `security/command_policy.json` into `execution/` (breaking change)
- Keep `security/` as the execution policy home and rename the plan section
- Have `execution/` reference `security/` by import

**Recommendation:** Keep `security/` as-is and create `execution/` as
a runtime dispatch layer that imports policy from `security/`. This
avoids breaking existing imports.

---

### 11. Evidence Graph Layer ✅

Already implemented:

```
.agentic-pi/runtime/evidence_indexer.py          ✅
.agentic-pi/runtime/evidence_freezer.py          ✅
.schemas/evidence_index.schema.json              ✅
.schemas/evidence_freeze.schema.json             ✅
.schemas/evidence_hash_manifest.schema.json      ✅
evidence_index.json                              ✅ (per run)
evidence_freeze.json                             ✅ (per run)
```

Evidence freeze rule is enforced: after EVIDENCE_INDEXING phase, frozen
evidence changes cause replay failure.

---

### 12. Policy / Replay / Certification Layer ✅

Already implemented:

```
Policy:
.agentic-pi/runtime/policy_engine.py             ✅
policy_decision.json                             ✅ (per run)

Replay:
.agentic-pi/replay/
├── replay_certification.py                      ✅
├── replay_rules.json                            ✅
└── validators/
    └── validate_replay_matches_policy.py        ✅

Certification:
.agentic-pi/validators/certify_run.py            ✅
.agentic-pi/schemas/final_status.schema.json     ✅
certification.json                               ✅ (per run)
final_status.json                                ✅ (per run)
final_status.md                                  ✅ (per run, derived)
tests/test_final_status_json_authority.py        ✅
```

**Correction to plan:** Phase 1 of the build order ("Add final_status.schema.json,
make certifier write final_status.json") is already complete. The proof
matrix entry `final_status_json_authority` proves it.

---

### 13. Repair / Escalation Layer 🔧 (new work)

Does not exist as a directory. The state machine supports repair states
(`REPAIRING_PLAN`, `REPAIRING_ARTIFACT_ROUTING`, `REPAIRING_VALIDATOR`,
`REPAIRING_EVIDENCE`, `REPAIRING_IMPLEMENTATION`) but there is no
dedicated `repair/` package with policy files and validators.

The plan describes:

```
.agentic-pi/repair/
├── repair_policy.json                   🔧
├── repair_attempts.jsonl               🔧
├── repair_packet.schema.json           🔧
└── validators/
    ├── validate_repair_scope.py        🔧
    └── validate_repair_budget.py       🔧
```

Building this layer means:
- Formalizing repair budget (max attempts per phase)
- Writing repair scope validators (repair cannot touch authority files)
- Connecting repair attempts to the dispatch ledger
- Tests: invalid repair scope is rejected, budget exhaustion blocks

---

### 14. Memory Layer ✅

Already implemented:

```
.agentic-pi/memory/
├── durable/                              ✅
├── run_local/                            ✅
├── quarantine/                           ✅
├── index/                                ✅
├── memory_policy.json                    ✅

.agentic-pi/runtime/run_memory_clerk.py          ✅
.agentic-pi/runtime/quarantine_memory_writer.py  ✅
.agentic-pi/runtime/memory_write_gate.py         ✅
.agentic-pi/runtime/mempalace_adapter.py         ✅
.agentic-pi/runtime/context_pack_builder.py      ✅
.agentic-pi/runtime/ace_reflector.py             ✅
.agentic-pi/runtime/ace_curator.py               ✅
```

Memory types match the plan:
1. Durable — written only after final status, advisory only ✅
2. Run-local — written during run, helps current repair, cannot certify ✅
3. Quarantine — candidate lessons, promoted through write gate ✅

Tests: `test_run_local_memory.py`, `test_quarantine_memory.py`,
`test_mempalace_adapter.py`, `test_context_pack_builder.py`,
`test_ace_reflector_curator.py`, `test_memory_write_gate.py`

---

### 15. Meta-Harness Evaluation Layer ✅

Already implemented:

```
.agentic-pi/diagnostics/meta_harness/
├── manifest.json                        ✅
└── run_meta_harness.py                  ✅

.agentic-pi/proof_matrix/proof_matrix.json        ✅ (28 entries)
.agentic-pi/runtime/run_proxy_matrix.py           ✅
.agentic-pi/diagnostics/evaluation/               ✅
.agentic-pi/diagnostics/trajectory_evaluation/    ✅
```

Adversarial cases from the plan that already have tests:

| Case | Test |
|---|---|
| file exists only -> NOT_DONE | `test_harness_runtime` |
| wrong artifact path -> blocked | `validate_artifact_location.py` |
| missing verifier -> NOT_DONE | `test_raw_goal_chain.py` |
| P0 self-test only -> PROVISIONAL_DONE | diagnostic evaluation |
| P2 certifying verifier -> CERTIFIED_DONE | `test_raw_goal_chain.py` |
| Mercury writes final_status.json -> fail | `test_runtime_enforcement.py` |
| Pi upgrades NOT_DONE -> MONITOR_FAIL | `test_pi_real_session_monitor.py` |
| memory as evidence -> fail | `test_evidence_freeze.py` |
| second repair beyond budget -> blocked | (no test yet — see §13) |
| selected branch without oracle -> blocked | (no test yet — new work) |
| always-pass validator -> untrusted | `validator_factory` tests |
| replay hash mismatch -> fail | `replay_certification.py` tests |

---

### 16. Skills Layer ✅

Already implemented (12 skills):

```
.agentic-pi/skills/
├── question-contract/          ✅
├── research-pack/              ✅
├── design-options/             ✅
├── structure-outline/          ✅
├── root-plan/                  ✅
├── artifact-contract/          ✅
├── validator-factory/          ✅
├── path-grounding/             ✅
├── harness-grill/              ✅
├── harness-tdd/                ✅
├── harness-diagnose/           ✅
├── harness-certify/            ✅
└── write-memory/               ✅
```

---

### — Security Layer ✅ (omitted from plan but exists)

```
.agentic-pi/security/
└── command_policy.json                  ✅
```

The plan's §13 places `command_policy.json` under an `execution/` directory
that does not exist. In the repo, it lives under `security/`. The plan
should either acknowledge this layer or explain the refactor.

---

## Corrected build order

The plan's build order has 9 phases. Phases 1, 4, 5, 6, 7, and 9
describe work that already exists. The corrected build order below
marks what is already proven and what actually needs building.

### Phase 1 — Authority status upgrade ✅ (DONE)

The proof matrix entry `final_status_json_authority` proves this is
already wired. What the plan describes ("Add final_status.schema.json,
make certifier write final_status.json") is done.

Verify: `python tests/test_final_status_json_authority.py -v`

### Phase 2 — Supervisor ledger ✅ (DONE)

Work packet schema, dispatch log, run state, phase queue — all exist.

Verify: `python tests/test_raw_goal_chain.py -v`

### Phase 3 — Artifact routing ✅ (DONE)

Schemas and all four validators exist.

Verify: `python .agentic-pi/artifacts/validators/validate_artifact_location.py` works on any run.

### Phase 4 — Success criteria + oracle mapping ✅ (DONE)

Compiler, registry, strength rules, validators — all exist.

Verify: `python -c "from success_criteria_compiler import compile_from_goal_contract"` imports cleanly.

### Phase 5 — Validator factory ✅ (DONE)

Meta-check, fixture runner, mutation runner, certifier — all exist.

Verify: `python .agentic-pi/validator_factory/runtime/certify_generated_validator.py --help`

### Phase 6 — Replay certification ✅ (DONE)

`replay_certification.py` exists and is wired into the kernel.
Changed evidence hash causes replay mismatch.

Verify: `python .agentic-pi/replay/replay_certification.py --help`

### Phase 7 — Memory split ✅ (DONE)

Three memory types exist. Write gate is enforced.

Verify: `python tests/test_memory_write_gate.py -v`

### Phase 8 — Meta-harness v0.1 ✅ (DONE)

15 adversarial cases partially covered. Some gaps remain:

| Missing test | Priority |
|---|---|
| Second repair beyond budget blocked | Medium |
| Selected branch without oracle mapping blocked | Medium |
| Always-pass generated validator untrusted | Low (exists in factory tests) |

Verify: `python .agentic-pi/runtime/run_proxy_matrix.py --mode quick`

### Phase 9 — QRSPI skill integration ✅ (DONE)

All 12 skills exist. The plan says "add small phase skills" — they already exist.

---

## What actually needs building

Only one item from the plan remains as genuinely new work:

### 🔧 Future: Project Adapter Layer (plan §4, none of the 9 phases)

Defer. Not needed for current harness operation.

### ✅ Already built

| Layer | Key files | Tests |
|---|---|---|
| Controlled Execution | `execution/write_scope_policy.json`, `execution/tool_registry.json`, `execution/network_policy.json`, 3 validators | 17 |
| Repair / Escalation | `repair/repair_policy.json`, `repair/repair_packet.schema.json`, 2 validators | 17 |
| Progressive Skill Dispatcher | `runtime/skill_dispatcher.py` — cumulative skill loading across phases | 16 |
| Skill → Kernel Wiring | `run_kernel.py` auto-injects accumulated skills into work packets | 7 |
| Horizontal Supervisor Loop | `runtime/supervisor_loop.py` — parallel dispatch within phase, vertical spine between phases | 17 |

---

## Updated runtime flow (corrected)

```
User raw goal
  ↓
Run Kernel creates run_id + ledger                     ✅
  ↓
Question phase creates question_contract.json          ✅
  ↓
Research phase creates research_pack.md                ✅
  ↓
Design phase creates design_options.json               ✅
  ↓
Structure phase creates structure_outline.json         ✅
  ↓
Success Criteria Compiler creates criteria set         ✅
  ↓
Oracle Mapper creates oracle_mapping.json              ✅
  ↓
Planner creates PlanGraph + branches                   ✅
  ↓
Artifact Contract Layer creates expected_artifacts     ✅
  ↓
Supervisor creates work packet                         ✅
  ↓
Fresh Mercury Engineer implements one packet           ✅
  ↓
Artifact validator checks location/content             ✅
  ↓
If failed, bounded repair packet                       🔧 (needs repair/)
  ↓
Validator Factory creates/certifies validator          ✅
  ↓
Verifier runs against frozen evidence                  ✅
  ↓
Policy engine decides final-status category            ✅
  ↓
Replay recomputes decision                              ✅
  ↓
Certifier writes certification.json + final_status.json  ✅
  ↓
[optional] Memory consolidator writes durable memory   ✅  (--skip-memory-update allowed)
  ↓
DONE                                                     ✅
```

---

## What the plan got right

The plan's architectural vision — layers, roles, statemachine, evidence-gated
policy, certifier final authority, memory write-back — **exactly matches**
what the repo already implements. The state names, file structures, role
assignments, and authority boundaries are all correct.

## What needed correction

| # | Issue | Fix applied |
|---|---|---|
| 1 | Version said v3.1, repo is v3.7 | Corrected header |
| 2 | "Now formalize core layer" — already done | Marked ✅ |
| 3 | "Phase 1 build: authority status" — already done | Marked ✅ |
| 4 | `execution/` doesn't exist | 🔧 new work |
| 5 | `repair/` doesn't exist | 🔧 new work |
| 6 | Build order phases describe existing work | Corrected build order |
| 7 | `security/` omitted | Added as layer — |
| 8 | `REPORTING -> DONE` skip not shown | Corrected flow |
| 9 | Authority violation is recoverable, not terminal | Corrected to repairable |

## How to verify this document against the harness

```cmd
python .agentic-pi/runtime/run_proxy_matrix.py --mode quick
python tests/test_raw_goal_chain.py -v
python tests/test_final_status_json_authority.py -v
python tests/test_runtime_enforcement.py -v
python tests/test_evidence_freeze.py -v
python tests/test_memory_write_gate.py -v
python tests/test_repo_structure_cleanup.py -v
```
