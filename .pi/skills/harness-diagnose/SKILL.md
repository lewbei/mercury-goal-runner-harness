---
name: harness-diagnose
description: When validation fails, produce a diagnostic report identifying the root cause. Advisory troubleshooting only — not for certifying.
---

# Harness Diagnose Skill

**Phase:** VALIDATING or BLOCKED phase
**Role:** Critic
**Artifact:** `diagnostic_report.json`

## Purpose

When a validation fails, produce a diagnostic report that identifies the root cause. This skill is for troubleshooting, not for certifying.

## Output Format

```json
{
  "diagnostic_id": "D.001",
  "trigger": "What validation failed",
  "root_cause": "Identified cause",
  "evidence": ["relevant log lines", "file state"],
  "recommended_action": "repair_plan / recreate_artifact / escalate",
  "severity": "warning/error/blocking"
}
```

## Validators Applied

- No validators — diagnostics are advisory only

## Authority Boundaries

- Do NOT change status
- Do NOT certify
- Do NOT claim DONE
- Diagnostic reports are not evidence
