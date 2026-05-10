# v3.7 MemPalace + ACE Memory Governance

## Summary

v3.7 upgrades the advisory memory layer into a structured, governed memory
system:

```text
MemPalace stores memory.
ACE reflects and proposes memory changes.
RPG-Harness governs memory promotion.
```

This implementation does not directly import or vendor the reference modules in
`modules/ace-main` or `modules/mempalace-develop`. Those folders are reference
material only. The harness implementation lives under `.agentic-pi/`.

## Core Invariant

```text
Memory can suggest.
Memory can help repair.
Memory can record what helped or harmed.
Memory cannot become evidence.
Memory cannot override policy.
Memory cannot certify DONE.
Final status still comes only from certify_run.py and policy_engine.py.
```

## Runtime Components

```text
.agentic-pi/runtime/mempalace_adapter.py
.agentic-pi/runtime/context_pack_builder.py
.agentic-pi/runtime/ace_reflector.py
.agentic-pi/runtime/ace_curator.py
.agentic-pi/runtime/memory_write_gate.py
```

Responsibilities:

```text
mempalace_adapter.py
  initializes durable memory layout
  reads and writes structured durable memory cards

context_pack_builder.py
  retrieves the smallest useful advisory card set
  filters deprecated, harmful, evidence-free, and authority-leaking cards

ace_reflector.py
  classifies used memory cards as helpful, harmful, or neutral
  cannot write durable memory

ace_curator.py
  writes curator delta candidates
  cannot write durable memory

memory_write_gate.py
  is the only v3.7 component that promotes cards to durable memory
  requires certifier-owned final_status.json first
```

## Validator Components

```text
.agentic-pi/validators/validate_memory_card.py
.agentic-pi/validators/validate_context_pack.py
.agentic-pi/validators/validate_memory_write_gate.py
.agentic-pi/validators/validate_memory_authority.py
.agentic-pi/validators/validate_memory_contradictions.py
```

The validators enforce:

```text
authority_level = advisory_only
can_certify_done = false
evidence_refs are required
context packs respect max_cards and max_tokens
curator candidates cannot directly write durable memory
memory_write_gate requires final_status.json
```

## Schemas

```text
.agentic-pi/schemas/mempalace_card.schema.json
.agentic-pi/schemas/context_pack.schema.json
.agentic-pi/schemas/reflection_report.schema.json
.agentic-pi/schemas/curator_delta.schema.json
.agentic-pi/schemas/memory_write_decision.schema.json
```

## Durable Memory Layout

```text
.agentic-pi/memory/
  durable/
    planning/
    verification/
    git_provenance/
    repair/
    anti_overclaim/
  index/
  verbatim/run_excerpts/
```

The durable layout follows the MemPalace idea of wings, rooms, drawers, and
cards, but the harness keeps the safety boundary tighter:

```text
durable cards are advisory only
cards require source_run_id
cards require evidence_refs
cards cannot cite themselves as authority
cards cannot enter evidence_index.json as proof
```

## ACE Flow

```text
context_pack.json is used during a run
memory_usage_log.jsonl records the cards used
ace_reflector.py marks cards helpful / harmful / neutral
ace_curator.py writes curator_delta_candidates.jsonl
memory_write_gate.py validates a candidate
only approved cards enter durable MemPalace memory
```

## Acceptance

```text
test_mempalace_adapter.py passes
test_context_pack_builder.py passes
test_ace_reflector_curator.py passes
test_memory_write_gate.py passes
proof_matrix quick mode includes v3.7 memory governance claims
```

## Claim Boundary

Safe claim:

```text
The harness now has structured advisory memory with gated durable promotion.
Memory can influence future strategy context, but only after validation and only
as advisory input.
```

Unsafe claim:

```text
Memory proves DONE.
Memory replaces frozen evidence.
ACE writes trusted durable memory by itself.
MemPalace can override policy or certification.
```

Those claims remain false.
