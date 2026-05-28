# v3.5 to v4.0 Authority, Evidence, Memory, and Evaluation Plan

Status: v3.5.0-v3.7 implemented locally; v3.8-v4.0 planned

This document updates the next roadmap using the local reference modules:

```text
modules/ace-main/
modules/mempalace-develop/
```

Those folders are ignored reference code, not vendored harness code. A clean
checkout must not require them. They are design references for memory and
self-improvement only.

## Core Invariant

```text
Who is allowed to certify DONE?

Pi can orchestrate.
Mercury can compile / execute / report.
Strategy can suggest.
Planner can select.
Memory can suggest.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

## Versioning Correction

The repo already uses:

```text
v3.2 = Runtime Enforcement Proof
v3.3 = RPG Harness Test Record
v3.4 = RPG Test Aggregation
```

Do not rename or overwrite those milestones.

The next sequence is:

```text
v3.5.0 = Authority Artifact Prerequisite (implemented)
v3.5   = Evidence Freeze + Evidence Index
v3.6   = Run-Local Memory + Quarantine Memory
v3.7   = MemPalace + ACE Memory Governance
v3.8   = Multi-Agent Context Board
v3.9   = External Host / Coding-Agent Integration
v4.0   = Paper-Style Evaluation Package
```

## Local Reference Modules

### ACE Reference

Local path:

```text
modules/ace-main/
```

Useful concepts observed from the reference code/docs:

```text
Generator
Reflector
Curator
playbook delta updates
helpful / harmful counters
deduplication / pruning
separate reflection from curation
```

Harness adaptation:

```text
ACE ideas become governance around memory updates.
They do not become certification authority.
They do not directly rewrite durable memory.
They propose memory deltas that must pass a memory write gate.
```

### MemPalace Reference

Local path:

```text
modules/mempalace-develop/
```

Useful concepts observed from the reference code/docs:

```text
local-first memory
verbatim drawers
wings and rooms
closets as compact pointer indexes
closet -> drawer hydration
scoped retrieval instead of dumping all memory
pluggable backend boundary
agent-specific wings / diaries
```

Harness adaptation:

```text
MemPalace ideas become a structured memory layout.
Memory stays advisory.
Retrieved cards become context-pack suggestions only.
Memory cannot enter frozen evidence as proof.
Memory cannot certify DONE.
```

## v3.5.0 - Authority Artifact Prerequisite

Implementation status:

```text
IMPLEMENTED
```

### Problem

The current repo still treats `final_status.md` as the visible final status
artifact. The next evidence-freeze layer needs a machine-readable authority
artifact before it can freeze and cite final status safely.

### Goal

Add:

```text
final_status.json = machine-readable authority artifact
final_status.md   = derived human-readable view only
```

### Files

```text
.agentic-pi/runtime/final_status_renderer.py
.agentic-pi/validators/validate_final_status.py
.agentic-pi/schemas/final_status.schema.json
tests/test_final_status_json_authority.py
```

### Microsteps

1. Define `final_status.schema.json`.
   - Required fields: `schema_version`, `run_id`, `status`, `status_source`,
     `policy_decision_path`, `certification_path`, `generated_at`.
   - Valid statuses: legacy `DONE_PASS` / `DONE_FAIL` and provenance
     `NOT_DONE` / `PROVISIONAL_DONE` / `CERTIFIED_DONE`.

2. Add `final_status_renderer.py`.
   - Render `final_status.md` from `final_status.json`.
   - Never parse Markdown to derive machine authority.

3. Update `certify_run.py`.
   - Write `policy_decision.json` when provenance mode applies.
   - Write `certification.json`.
   - Write `final_status.json`.
   - Render `final_status.md` from `final_status.json`.

4. Add validator behavior.
   - Reject `certification.json` and `final_status.json` mismatch.
   - Reject `policy_decision.json` and certification status mismatch in
     provenance mode.
   - Treat Markdown as display-only.

5. Add regression fixtures.
   - `final_status.md = CERTIFIED_DONE` while `final_status.json = NOT_DONE`
     must remain `NOT_DONE`.
   - Missing `final_status.json` can fall back only for legacy compatibility,
     not for new provenance certification.

### Acceptance

```text
certification.json and final_status.json agree.
final_status.md is derived from final_status.json.
Markdown cannot upgrade JSON authority.
Existing legacy tests remain compatible.
```

## v3.5 - Evidence Freeze + Evidence Index

### Problem

Evidence exists across many files:

```text
trace.jsonl
step_logs/
artifacts/
verifier_artifacts/
verifier_smell_reports/
verifier_strength_reports/
run_manifest.json
replay_report.json
policy_decision.json
certification.json
final_status.json
```

The certifier checks many of these, but there is no single frozen
producer-linked evidence boundary.

### Goal

Create:

```text
evidence_index.json
evidence_freeze.json
evidence_hash_manifest.json
```

Every certifiable claim must cite frozen producer-linked evidence.

### Files

```text
.agentic-pi/runtime/evidence_indexer.py
.agentic-pi/runtime/evidence_freezer.py
.agentic-pi/validators/validate_evidence_index.py
.agentic-pi/validators/validate_evidence_freeze.py
.agentic-pi/schemas/evidence_index.schema.json
.agentic-pi/schemas/evidence_freeze.schema.json
.agentic-pi/schemas/evidence_hash_manifest.schema.json
tests/test_evidence_freeze.py
```

### Evidence Lifecycle

```text
execution
  -> trace + logs + artifacts
  -> verifier artifacts
  -> smell + strength reports
  -> policy decision
  -> evidence index
  -> evidence freeze
  -> certification cites freeze
  -> replay uses frozen evidence only
```

### Microsteps

1. Index evidence.
   - Include path, hash, kind, producer, producer command id, trust level,
     created-before-freeze flag.

2. Link policy claims to evidence.
   - Each `policy_decision.json` certifying artifact must map to an indexed
     `verifier_artifact` item.
   - Each verifier strength/smell claim must map to indexed reports.

3. Freeze evidence.
   - Generate `freeze_id`.
   - Write `evidence_hash_manifest.json`.
   - Write `evidence_freeze.json` after policy decision and before final
     status authority is accepted.

4. Reject unsafe evidence timing.
   - Freeze before policy is invalid.
   - Evidence created after freeze is not certifying evidence.
   - Mutation after freeze is detected through hash mismatch.

5. Connect replay.
   - Replay must read frozen evidence and reject mismatches.
   - Replay can block certification.
   - Replay cannot certify DONE by itself.

### Required Tests

```text
test_evidence_index_contains_trace
test_evidence_index_contains_step_logs
test_evidence_index_contains_verifier_artifacts
test_every_policy_claim_cites_evidence
test_memory_cannot_enter_evidence_index
test_mutation_after_freeze_detected
test_missing_producer_blocks_certification
test_hash_mismatch_blocks_certification
test_freeze_before_policy_rejected
```

## v3.6 - Run-Local Memory + Quarantine Memory

### Problem

Experience memory is safe and advisory, but mostly post-run. If memory writes
only after certification, it is too late for within-run adaptation.

### Goal

Split memory into:

```text
run-local working memory
quarantine learning memory
durable memory
```

The current run may learn locally. Future runs cannot use the lesson until it
passes the memory write gate.

### Files

```text
.agentic-pi/runtime/run_memory_clerk.py
.agentic-pi/runtime/quarantine_memory_writer.py
.agentic-pi/validators/validate_run_local_memory.py
.agentic-pi/validators/validate_quarantine_memory.py
.agentic-pi/schemas/run_journal_entry.schema.json
.agentic-pi/schemas/learning_candidate.schema.json
tests/test_run_local_memory.py
tests/test_quarantine_memory.py
```

### Run-Local Files

```text
.agentic-runs/<run_id>/memory/run_journal.jsonl
.agentic-runs/<run_id>/memory/phase_observations.jsonl
.agentic-runs/<run_id>/memory/failure_observations.jsonl
.agentic-runs/<run_id>/memory/repair_notes.jsonl
.agentic-runs/<run_id>/memory/context_updates.jsonl
.agentic-runs/<run_id>/memory/memory_usage_log.jsonl
.agentic-runs/<run_id>/memory/memory_effect_log.jsonl
```

### Quarantine Files

```text
.agentic-runs/<run_id>/memory/learning_candidates.jsonl
.agentic-runs/<run_id>/memory/curator_delta_candidates.jsonl
.agentic-runs/<run_id>/memory/rejected_learning_candidates.jsonl
.agentic-runs/<run_id>/memory/pending_memory_promotions.jsonl
```

### Rules

Run-local memory can:

```text
help repair
record failure observations
record context drift
record memory usage
record candidate lessons
```

Run-local memory cannot:

```text
certify
replace evidence
enter evidence_index.json
write final_status.json
write certification.json
write policy_decision.json
```

### Required Tests

```text
test_run_local_memory_appends_during_planning
test_run_local_memory_appends_during_execution
test_run_local_memory_appends_after_verifier_failure
test_run_local_memory_cannot_write_authority_artifacts
test_run_local_memory_cannot_enter_evidence_index
test_quarantine_memory_not_retrieved_by_future_runs
test_quarantine_memory_requires_source_run_id
```

## v3.7 - MemPalace + ACE Memory Governance

### Problem

The current advisory memory is intentionally basic. The desired memory style is
stronger:

```text
MemPalace = wings / rooms / closets / drawers / cards / indexes
ACE       = Generator / Reflector / Curator / playbook deltas / helpful-harmful counters
```

### Goal

Upgrade experience memory into structured evolving memory:

```text
MemPalace stores memory.
ACE evolves memory.
RPG-Harness governs memory.
```

### Files

```text
.agentic-pi/runtime/mempalace_adapter.py
.agentic-pi/runtime/context_pack_builder.py
.agentic-pi/runtime/ace_reflector.py
.agentic-pi/runtime/ace_curator.py
.agentic-pi/runtime/memory_write_gate.py
.agentic-pi/validators/validate_memory_card.py
.agentic-pi/validators/validate_context_pack.py
.agentic-pi/validators/validate_memory_write_gate.py
.agentic-pi/validators/validate_memory_authority.py
.agentic-pi/validators/validate_memory_contradictions.py
.agentic-pi/schemas/mempalace_card.schema.json
.agentic-pi/schemas/context_pack.schema.json
.agentic-pi/schemas/reflection_report.schema.json
.agentic-pi/schemas/curator_delta.schema.json
.agentic-pi/schemas/memory_write_decision.schema.json
tests/test_mempalace_adapter.py
tests/test_context_pack_builder.py
tests/test_ace_reflector_curator.py
tests/test_memory_write_gate.py
```

### Durable Layout

```text
.agentic-pi/memory/durable/planning/
.agentic-pi/memory/durable/verification/
.agentic-pi/memory/durable/git_provenance/
.agentic-pi/memory/durable/repair/
.agentic-pi/memory/durable/anti_overclaim/
.agentic-pi/memory/index/
.agentic-pi/memory/verbatim/run_excerpts/
```

### Adapted MemPalace Mapping

```text
wing   = broad harness domain, e.g. anti_overclaim
room   = topic within wing, e.g. artifact_exists_not_done
drawer = source-backed run excerpt or record pointer
closet = compact pointer index to drawers/cards
card   = curated advisory lesson with evidence refs
```

### Adapted ACE Flow

```text
worker uses context pack
  -> memory_usage_log.jsonl records used cards
  -> run succeeds / fails / becomes provisional
  -> ace_reflector.py marks what helped or harmed
  -> ace_curator.py proposes card deltas
  -> memory_write_gate.py validates candidates
  -> approved cards enter durable MemPalace
```

### Required Tests

```text
test_memory_card_requires_evidence_refs
test_context_pack_respects_max_cards
test_context_pack_excludes_deprecated_cards
test_context_pack_excludes_harmful_cards
test_ace_reflector_marks_helpful_memory
test_ace_reflector_marks_harmful_memory
test_curator_candidate_cannot_directly_write_durable_memory
test_memory_write_gate_rejects_authority_leakage
test_memory_write_gate_rejects_no_evidence_ref
test_memory_write_gate_promotes_valid_card_after_final_status_json
```

### Acceptance

```text
Memory becomes structured and adaptive.
Memory still cannot certify.
Memory still cannot bypass policy.
Memory still cannot replace frozen evidence.
```

## v3.8 - Multi-Agent Context Board

### Goal

Let many agents coordinate through structured artifacts, not raw context dumps.

### Files

```text
[PLANNED - not yet implemented]
.agentic-pi/runtime/context_board.py
.agentic-pi/runtime/worker_report_writer.py
.agentic-pi/runtime/finding_card_writer.py
.agentic-pi/validators/validate_context_board.py
.agentic-pi/validators/validate_worker_report.py
.agentic-pi/schemas/task_board.schema.json
.agentic-pi/schemas/worker_report.schema.json
.agentic-pi/schemas/finding_card.schema.json
.agentic-pi/schemas/risk_card.schema.json
tests/test_context_board.py
```

### Rules

Agents share:

```text
cards
summaries
artifacts
evidence refs
task state
```

Agents do not share:

```text
raw messy context
private chain-of-thought
authority decisions
final status edits
```

### Required Tests

```text
test_worker_report_cannot_claim_certified_done
test_finding_card_requires_evidence_ref
test_risk_card_can_block_selection_if_critical
test_agent_cannot_write_policy_decision
test_agent_cannot_write_certification
test_agent_cannot_write_final_status_json
test_context_board_does_not_enter_evidence_index_as_proof
```

## v3.9 - External Host / Coding-Agent Integration

### Goal

Allow external coding agents to work inside the harness without giving them
authority.

### Supported Adapters

```text
Pi adapter
Mercury adapter
Claude Code adapter
Codex adapter
Hermes adapter
generic CLI agent adapter
```

### Files

```text
[PLANNED - not yet implemented]
.agentic-pi/adapters/agent_adapter.schema.json
.agentic-pi/adapters/generic_cli_adapter.py
.agentic-pi/adapters/claude_code_adapter.py
.agentic-pi/adapters/codex_adapter.py
.agentic-pi/adapters/pi_adapter.py
.agentic-pi/validators/validate_agent_adapter.py
.agentic-pi/validators/validate_adapter_authority.py
tests/test_agent_adapters.py
```

### Required Tests

```text
test_adapter_cannot_write_authority_artifacts
test_adapter_cannot_escape_worktree
test_adapter_output_schema_validated
test_adapter_transcript_hash_recorded
test_adapter_role_binding_enforced
test_external_agent_report_overclaim_rejected
```

### Acceptance

```text
External agents are workers, not certifiers.
```

## v4.0 - Paper-Style Evaluation Package

### Goal

Turn the harness into a publishable evaluation framework:

```text
false DONE prevention
verifier provenance
agent authority separation
prompt-attack behavior matrix
reproducibility evidence
```

### Evaluation Groups

```text
Group A: deterministic false-DONE fixtures
Group B: verifier-provenance authority fixtures
Group C: command-policy negative probes
Group D: Git provenance replay probes
Group E: memory-as-authority probes
Group F: real Pi/Mercury prompt matrix
Group G: external coding-agent adapter probes
```

### Main Metrics

```text
false_CERTIFIED_DONE_rate
false_PROVISIONAL_DONE_rate
unsafe_attempt_missed_count
safe_refusal_count
authority_violation_block_rate
replay_match_rate
evidence_freeze_mismatch_detection_rate
memory_authority_leak_rate
command_policy_block_rate
Git_reconstructability_rate
```

### Files

```text
evaluation/suites/false_done/
evaluation/suites/verifier_provenance/
evaluation/suites/command_policy/
evaluation/suites/git_provenance/
evaluation/suites/memory_authority/
evaluation/suites/real_pi_prompt_matrix/
evaluation/run_all_evaluations.py
evaluation/summarize_results.py
evaluation/paper_tables/
```

### Paper Claim Boundary

Safe claim:

```text
The harness reduces false certified-DONE outcomes by separating agent
execution, verifier provenance, deterministic policy, replay, frozen evidence,
and final authority artifacts.
```

Unsafe claim:

```text
The harness proves arbitrary autonomous agents are safe.
```

Do not claim that.

## Updated Architecture

```text
USER RAW GOAL
  -> GOAL CONTRACT LAYER
  -> STRATEGY / PLANNING LAYER
  -> CONTEXT / MEMORY LAYER
  -> COMMAND POLICY LAYER
  -> GIT WORKTREE EXECUTION
  -> EVIDENCE FREEZE LAYER
  -> POLICY / REPLAY / CERTIFIER
  -> ACE + MEMPALACE UPDATE
  -> REPORT / PAPER TABLES
```

## Recommended Implementation Order

```text
1. v3.5.0 final_status.json authority
2. v3.5 evidence freeze
3. v3.6 run-local / quarantine memory
4. v3.7 MemPalace + ACE
5. v3.8 multi-agent context board
6. v3.9 external adapters
7. v4.0 paper-style evaluation package
```

Reason:

```text
Memory becomes dangerous if authority is not hardened first.
Multi-agent control becomes dangerous if command policy and evidence freeze are
not hardened first.
Paper claims become weak if evidence replay is not frozen and reproducible.
```

## Test Gate Policy

For narrow docs/schema/reporting slices:

```cmd
python <focused tests> -v
python .agentic-pi\runtime\run_proof_matrix.py --mode quick
git diff --check
```

For certifier, policy, authority artifact, evidence freeze, command policy, or
adapter enforcement changes:

```cmd
python <focused tests> -v
python -m unittest discover tests -v
python .agentic-pi\diagnostics\evaluation\run_diagnostic_evaluation.py
python .agentic-pi\diagnostics\trajectory_evaluation\run_trajectory_evaluation.py
python .agentic-pi\benchmark\run_benchmark.py
git diff --check
```

## Final Architecture Sentence

```text
Mercury Goal Runner Harness is evolving into a verifier-provenance control
plane where agents may plan, execute, repair, and report, but certification
depends only on frozen evidence, deterministic policy, replayable provenance,
and machine-readable final authority.
```
