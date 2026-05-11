---
name: design-options
description: Produce alternative design approaches for the goal. Each option includes trade-offs, feasibility assessment, and alignment with success criteria.
---

# Design Options Skill

**Phase:** DESIGNING
**Role:** Designer
**Artifact:** `artifacts/design_options.json`

## Purpose

Produce alternative design approaches for the goal. Each option includes trade-offs, feasibility assessment, and alignment with success criteria.

## Output Schema

Valid JSON array of design option objects:

```json
[
  {
    "option_id": "OPT.001",
    "title": "Option title",
    "description": "Brief description",
    "approach": "Technical approach",
    "pros": ["advantage 1", "advantage 2"],
    "cons": ["disadvantage 1"],
    "estimated_effort": "small/medium/large",
    "alignment_with_criteria": ["SC.001", "SC.002"],
    "risks": ["risk 1"]
  }
]
```

## Validators Applied

- `.agentic-pi/artifacts/validators/validate_artifact_location.py` — checks file exists
- `.agentic-pi/artifacts/validators/validate_artifact_satisfaction.py` — checks valid JSON and non-empty

## Authority Boundaries

- Do NOT select a design — only propose options
- Do NOT write authority files
- Do NOT certify
