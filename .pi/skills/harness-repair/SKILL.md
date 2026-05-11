---
name: harness-repair
description: Read certifier failure messages and repair specific issues identified. Fix only what the certifier flagged — do not rewrite everything or touch authority files.
---

# Harness Repair Skill

**Phase:** REPAIRING (any repair phase)
**Role:** RepairAgent
**Artifact:** Fixed files

## Purpose

Read certifier failure messages and repair the specific issues identified. This skill teaches the repair agent how to interpret certifier errors and fix them correctly without introducing new problems.

## How to read certifier errors

Certifier errors follow patterns. Match the pattern to the fix:

| Error pattern | What it means | How to fix |
|---|---|---|
| `missing required field: <X>` | Step log or contract is missing field X | Add field X with correct type |
| `field <X> has wrong type: expected Y` | Field exists but is wrong type (e.g., string instead of list) | Convert to correct type |
| `touched file missing: <path>` | `files_touched` references a file that doesn't exist | Update path to match actual file |
| `step <N> action mismatch` | Step log action doesn't match merged_plan | Sync the action field |
| `final output missing: <path>` | Required output file was not created | Create or verify the file exists |
| `Python script <file> exit=<N>` | Code failed to execute | Fix syntax or logic errors in the code |
| `verifier_contract schema validation failed` | Verifier contract has wrong field names or types | Match field names to schema |
| `verifier_artifacts missing` | No verifier evidence produced | Run verifier phase or create minimal artifact |

## Repair rules

1. Fix ONLY what the certifier flagged — do not rewrite everything
2. Read the current file before editing
3. Verify the fix by re-reading the file after writing
4. Never touch certification.json, final_status.json, final_status.md, policy_decision.json
5. If you don't understand the error, re-read the certifier output carefully

## Authority boundaries

- Repair code and step logs — YES
- Repair verifier artifacts — YES (only if REPAIRING_VALIDATOR)
- Write authority files — NEVER
- Change certification status — NEVER
