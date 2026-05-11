---
name: validator-factory
description: Generate a validator spec and code for a specific success criterion. The validator must be testable with positive and negative fixtures through the V0_PROPOSED lifecycle.
---

# Validator Factory Skill

**Phase:** VALIDATOR_BUILDING
**Role:** ValidatorEngineer
**Artifact:** `validator_spec.json` (in run directory) + validator code file

## Purpose

Generate a validator spec and code for a specific success criterion. The validator must be testable with positive and negative fixtures.

## Output Requirements

1. **Validator Spec** — valid JSON conforming to `validator_spec.schema.json`
2. **Validator Code** — Python script with `def check(input) -> bool` that returns PASS/FAIL
3. **Fixture Suite** — JSON conforming to `fixture_suite.schema.json` with at least 2 positive and 2 negative fixtures

## Lifecycle

```
V0_PROPOSED (generated) -> meta-check -> fixture tests -> mutation tests -> V1 or V2
```

## Validators Applied

- `.agentic-pi/validator_factory/runtime/run_validator_meta_check.py`
- `.agentic-pi/validator_factory/runtime/run_validator_fixtures.py`
- `.agentic-pi/validator_factory/runtime/run_validator_mutations.py`
- `.agentic-pi/validator_factory/runtime/certify_generated_validator.py`

## Authority Boundaries

- Do NOT certify or claim DONE
- Generated validator starts at V0_PROPOSED — never assume certification
- Do NOT skip meta-check
- Do NOT claim the validator is trusted before certification
- Do NOT write authority files
