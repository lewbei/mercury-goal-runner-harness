# Harness Certify Skill

**Phase:** CERTIFYING
**Role:** Certifier (deterministic core only)
**Artifact:** `certification.json` + `final_status.json` + `final_status.md`

## Purpose

Write the final status artifacts. This is the only skill that writes authority files. It is NOT available to Mercury agents — it is a deterministic core operation.

## Process

1. Read `policy_decision.json` — the policy engine has already decided
2. Read verifier evidence, smell reports, strength reports
3. Compute final status: NOT_DONE / PROVISIONAL_DONE / CERTIFIED_DONE / DONE_PASS / DONE_FAIL
4. Write `certification.json` with full check results
5. Write `final_status.json` with authority marker `certifier_only`
6. Render `final_status.md` from `final_status.json`

## Core Rule

```
final_status.json = authority artifact (machine-readable, certifier-only)
final_status.md   = derived view (human-readable)
```

Only `certify_run.py` / `policy_engine.py` may call this skill.

## Authority Claim

```text
Who is allowed to certify DONE?
- Pi can orchestrate.
- Mercury can compile / execute / report.
- Policy decides.
- Certifier writes final status.
- Pi only reports what the certifier wrote.
```

## Validators

- `.agentic-pi/validators/certify_run.py` — full certification pipeline
- `.agentic-pi/validators/validate_final_status.py` — schema + consistency with certification.json and policy_decision.json
- `.agentic-pi/runtime/final_status_renderer.py` — renders markdown from JSON
