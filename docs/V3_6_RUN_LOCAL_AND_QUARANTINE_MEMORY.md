# v3.6 Run-Local Memory + Quarantine Memory

## Claim

v3.6 adds current-run memory without turning memory into evidence or
authority.

```text
Memory can suggest.
Memory can record current-run observations.
Memory cannot certify.
Memory cannot replace evidence.
Memory cannot enter evidence_index.json.
Policy decides.
certify_run.py writes final status.
Pi/Mercury only report what the certifier wrote.
```

## Run-Local Memory

Run-local memory is written only under:

```text
.agentic-runs/<run_id>/memory/
```

The current files are:

```text
run_journal.jsonl
phase_observations.jsonl
failure_observations.jsonl
repair_notes.jsonl
context_updates.jsonl
memory_usage_log.jsonl
memory_effect_log.jsonl
```

`run_memory_clerk.py` appends advisory JSONL entries for planning,
execution, verifier failure, repair, context updates, memory usage, and memory
effect observations.

Every entry records:

```text
memory_scope = run_local
durable = false
excluded_from_evidence_index = true
authority_level = advisory_only
final_status_authority = certifier_only
can_certify_done = false
```

The clerk rejects target files that are protected authority or evidence-freeze
artifacts:

```text
final_status.json
final_status.md
certification.json
policy_decision.json
evidence_index.json
evidence_freeze.json
evidence_hash_manifest.json
```

## Quarantine Memory

Quarantine memory is also run-local. It holds candidate lessons until a later
memory-governance slice decides whether they may become durable.

The current quarantine files are:

```text
learning_candidates.jsonl
curator_delta_candidates.jsonl
rejected_learning_candidates.jsonl
pending_memory_promotions.jsonl
```

Every candidate requires `source_run_id` and records:

```text
memory_scope = quarantine
durable = false
retrievable_by_future_runs = false
authority_level = advisory_only
final_status_authority = certifier_only
can_certify_done = false
```

## Boundary

This slice does not implement MemPalace, ACE curator behavior, durable memory,
multi-agent context board, external adapters, or paper evaluation.

The safe claim is:

```text
The current run may learn locally, but future runs cannot use the lesson until
it passes a later memory write gate.
```

The unsafe claim is:

```text
Memory is evidence, policy, certification, or final status.
```
