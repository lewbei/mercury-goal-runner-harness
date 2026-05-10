# Write Memory Skill

**Phase:** MEMORY_CONSOLIDATING
**Role:** MemoryWriter
**Artifact:** `memory_write_proposal.json`

## Purpose

Write advisory durable memory after the final status is locked. Memory records lessons learned, patterns observed, and context for future runs.

## Constraints

1. **Final status must be locked first** — `final_status.json` must exist and be valid
2. **Memory is advisory** — cannot replace evidence, override policy, or alter certification
3. **Memory is not evidence** — excluded from evidence_index.json and evidence_freeze.json

## Output Schema

Valid JSON conforming to `learning_candidate.schema.json` or `run_journal_entry.schema.json`:

```json
{
  "memory_type": "learning_candidate",
  "source_run_id": "run_001",
  "observation": "What was learned",
  "context": "Goal type, phase, relevant criteria",
  "category": "pattern/failure/success/constraint",
  "confidence": "high/medium/low"
}
```

## Promotion Gate

- Quarantine memory → promoted through `memory_write_gate.py`
- Run-local memory → archived when run completes
- Durable memory → written only after gate passes

## Authority Boundaries

- Memory cannot certify current run
- Memory cannot override policy_decision.json
- Memory cannot appear in evidence_freeze.json
- Memory fields must not contain authority-leak fields (final_status, certified_done, policy_override)
