---
name: question-contract
description: Convert a raw user goal into a structured question contract defining what the goal is, why it matters, and what success looks like in measurable terms.
---

# Question Contract Skill

**Phase:** INTAKE / QUESTIONING
**Role:** Questioner
**Artifact:** `artifacts/question_contract.json`

## Purpose

Convert a raw user goal into a structured question contract. The contract defines what the goal is, why it matters, and what success looks like in measurable terms.

## Output Schema

The artifact must be valid JSON conforming to `goal_contract.schema.json`.

Required fields:
- `goal_id` — unique identifier
- `goal_type` — one of: coding, test, research, document, generic
- `description` — clear single-paragraph goal description
- `success_criteria` — array of strings or criterion objects (see success criteria skill)
- `constraints` — array of constraint strings (optional)

## Validators Applied

- `.agentic-pi/validators/validate_goal_contract.py` — schema validation
- `.agentic-pi/success/validators/validate_success_measurability.py` — checks criteria are measurable

## Authority Boundaries

- Do NOT write `final_status.json`, `certification.json`, `policy_decision.json`
- Do NOT claim DONE
- Do NOT include policy or certification status in the contract

## Example

```json
{
  "goal_id": "example_001",
  "goal_type": "coding",
  "description": "Create a JSON report generator",
  "success_criteria": ["Output file exists at artifacts/report.json", "Report is valid JSON"],
  "constraints": ["Must use Python 3"]
}
```
