---
name: artifact-contract
description: Prepare the controlled workspace before implementation begins. Define expected artifacts, their paths, and writing permissions in an explicit artifact contract.
---

# Artifact Contract Skill

**Phase:** WORKTREE_READY
**Role:** Engineer (planning stage)
**Artifact:** `artifacts/workspace_manifest.json`

## Purpose

Prepare the controlled workspace before implementation begins. Define expected artifacts, their paths, and writing permissions. This makes the artifact contract explicit before any code is written.

## Output Schema

Valid JSON following `expected_artifacts.schema.json`:

```json
{
  "workspace_path": ".agentic-runs/<run_id>/",
  "expected_artifacts": [
    {
      "artifact_id": "A.REPORT",
      "expected_path": "artifacts/report.json",
      "required": true,
      "allowed_writers": ["Engineer"],
      "forbidden_writers": ["Reporter", "Critic"],
      "success_criteria": ["SC.001"]
    }
  ]
}
```

## Validators Applied

- `.agentic-pi/artifacts/validators/validate_expected_artifacts.py` — schema + internal consistency
- `.agentic-pi/artifacts/artifact_placement_policy.json` — placement rules

## Authority Boundaries

- Do NOT write artifacts yet — only declare contracts
- Do NOT certify
- Do NOT write final_status.json
