---
name: research-pack
description: Gather relevant context, dependencies, and prior work related to the goal. The research pack informs design decisions and prevents rework.
---

# Research Pack Skill

**Phase:** RESEARCHING
**Role:** Researcher
**Artifact:** `artifacts/research_pack.md`

## Purpose

Gather relevant context, dependencies, and prior work related to the goal. The research pack informs design decisions and prevents rework.

## Output Format

Markdown file with sections:
- **Context** — relevant files, modules, or systems
- **Dependencies** — libraries, tools, or data sources needed
- **Prior Art** — existing solutions, patterns, or examples
- **Risks** — known issues or challenges
- **References** — links or citations

## Validators Applied

- `.agentic-pi/artifacts/validators/validate_artifact_location.py` — checks file exists at expected path
- `.agentic-pi/artifacts/validators/validate_artifact_satisfaction.py` — checks file non-empty

## Authority Boundaries

- Do NOT write `final_status.json`, `certification.json`, or any authority files
- Do NOT certify or claim DONE
- Do NOT implement — research only
