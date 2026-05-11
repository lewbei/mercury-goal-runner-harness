---
name: path-grounding
description: Before writing any code, ground the implementation in expected artifact paths from the artifact contract. Every file written must match its declared expected path.
---

# Path Grounding Skill

**Phase:** IMPLEMENTING (first step)
**Role:** Engineer
**Artifact:** Only reference — no standalone artifact

## Purpose

Before writing any code, ground the implementation in the expected artifact paths from the artifact contract. Every file written must match its declared expected path.

## Rules

1. Read `expected_artifacts.json` from the run directory
2. Every file you create must be at its declared `expected_path`
3. If the contract says `artifacts/report.json`, do NOT write `report.json`
4. Do NOT write files outside your `allowed_write_paths`
5. Do NOT write to `forbidden_write_paths` (especially authority files)

## Validation

- `.agentic-pi/artifacts/validators/validate_artifact_location.py` — run this after writing to confirm placement

## Authority Boundaries

- Do NOT certify or claim DONE
- Engineer writes implementation files only
- Do NOT write: final_status.json, certification.json, policy_decision.json, evidence_freeze.json
- If unsure about a path, check the contract first
