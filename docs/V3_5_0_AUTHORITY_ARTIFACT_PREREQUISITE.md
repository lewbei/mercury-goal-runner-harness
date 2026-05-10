# v3.5.0 Authority Artifact Prerequisite

AUTHORITY ARTIFACT PREREQUISITE IMPLEMENTED

## Goal

Add a machine-readable final authority artifact:

```text
final_status.json = machine-readable authority
final_status.md   = derived human-readable view
```

This slice keeps the central question unchanged:

```text
Who is allowed to certify DONE?
```

## What Changed

Added:

```text
.agentic-pi/runtime/final_status_renderer.py
.agentic-pi/validators/validate_final_status.py
.agentic-pi/schemas/final_status.schema.json
tests/test_final_status_json_authority.py
```

Updated:

```text
.agentic-pi/validators/certify_run.py
```

The certifier now writes:

```text
certification.json
final_status.json
final_status.md
```

`final_status.md` is rendered from `final_status.json`. It is not authority.

## Authority Rule

```text
certification.json and final_status.json must agree.
final_status.md cannot upgrade machine authority.
policy_decision.json -> certification.json -> final_status.json must be consistent in provenance mode.
```

If:

```text
final_status.md = CERTIFIED_DONE
final_status.json = NOT_DONE
```

then authority remains:

```text
NOT_DONE
```

## Machine-Readable Fields

```json
{
  "schema_version": "final_status_v1",
  "run_id": "run_id",
  "status": "CERTIFIED_DONE",
  "status_source": "policy_decision.json",
  "final_status_authority": "certifier_only",
  "can_certify_done": false,
  "policy_decision_path": "policy_decision.json",
  "certification_path": "certification.json",
  "generated_at": "timestamp"
}
```

## Boundary

This slice does not implement:

```text
evidence freeze
run-local memory
quarantine memory
MemPalace
ACE
multi-agent context board
external adapters
paper-style evaluation
```

Those remain planned in:

```text
docs/V3_5_TO_V4_0_AUTHORITY_EVIDENCE_MEMORY_PLAN.md
```

## Safe Claim

```text
v3.5.0 makes final status machine-readable and certifier-owned.
Markdown is now display-only and cannot upgrade final authority.
```

## Unsafe Claim

```text
v3.5.0 proves arbitrary Pi/Mercury autonomy is safe.
```

Do not claim that.

## Proof

Focused proof command:

```cmd
python tests\test_final_status_json_authority.py -v
```

The focused tests prove:

```text
final_status.json is written by certify_run.py
final_status.md is rendered from final_status.json
Markdown cannot upgrade JSON authority
certification.json and final_status.json agree
policy_decision.json -> certification.json -> final_status.json is consistent
legacy DONE_PASS / DONE_FAIL remains supported
```
