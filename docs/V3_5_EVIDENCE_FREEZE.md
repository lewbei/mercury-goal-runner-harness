# v3.5 Evidence Freeze

This slice adds the frozen evidence boundary that sits between
`policy_decision.json` and `certification.json`.

Core invariant:

```text
Who is allowed to certify DONE?
Mercury can compile / execute / report.
Policy decides.
certify_run.py writes final status.
Pi/Mercury only report what the certifier wrote.
```

## Files

```text
evidence_index.json
evidence_freeze.json
evidence_hash_manifest.json
```

`evidence_index.json` records producer-linked evidence:

```text
trace.jsonl
step_logs/
artifacts/
verifier_artifacts/
verifier_smell_reports/
verifier_strength_reports/
policy_decision.json
certification.json, when already present
final_status.json, when already present
```

Memory files are deliberately excluded. Memory can suggest, but memory cannot
become evidence and cannot certify DONE.

## Lifecycle

```text
execution
-> trace + logs + artifacts
-> verifier artifacts
-> smell + strength reports
-> policy_decision.json
-> evidence_index.json
-> evidence_freeze.json
-> evidence_hash_manifest.json
-> certification.json
-> final_status.json
-> final_status.md
```

The freeze is allowed to block certification if evidence is missing, mutated, or
not producer-linked. It is not allowed to certify DONE by itself.

## Validation Rules

```text
Every evidence item has:
  evidence_id
  kind
  path
  sha256
  producer
  producer_command_id
  trust_level
  created_before_freeze

Every certifying/provisional policy artifact ID must map to an indexed
VERIFIER_ARTIFACT item.

policy_decision.json must exist before evidence_freeze.json can be written.

Post-freeze mutation is detected by evidence_hash_manifest.json.
```

Safe claim:

```text
The harness now indexes and freezes producer-linked evidence before certifier
authority is written, and detects missing producers, missing policy evidence,
memory-as-evidence attempts, and hash mismatches.
```

Unsafe claim:

```text
This does not prove arbitrary prompt coverage, full Pi autonomy, or arbitrary
unbounded bash safety.
```
