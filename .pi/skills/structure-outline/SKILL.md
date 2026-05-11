---
name: structure-outline
description: Define the structural components needed to implement the selected design. Maps design options to concrete files, modules, tests, and configurations.
---

# Structure Outline Skill

**Phase:** STRUCTURING
**Role:** Structurer
**Artifact:** `artifacts/structure_outline.json`

## Purpose

Define the structural components needed to implement the selected design. Maps design options to concrete files, modules, tests, and configurations.

## Output Schema

Valid JSON with:

```json
{
  "components": [
    {
      "component_id": "C.001",
      "name": "component name",
      "type": "module/file/test/config",
      "path": "relative/path",
      "dependencies": ["C.002"],
      "description": "What this component does"
    }
  ],
  "interfaces": [],
  "data_flow": []
}
```

## Validators Applied

- `.agentic-pi/artifacts/validators/validate_artifact_location.py`
- `.agentic-pi/artifacts/validators/validate_artifact_satisfaction.py`

## Authority Boundaries

- Do NOT implement — structure only
- Do NOT write authority files
- Do NOT certify
