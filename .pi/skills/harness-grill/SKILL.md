# Harness Grill Skill

**Phase:** VALIDATING
**Role:** Critic
**Artifact:** `verifier_artifacts/` directory

## Purpose

Run existing validators against the implementation artifacts and produce verifier evidence. Each verifier artifact is a JSON file recording the check, the input, the expected output, and the actual result.

## Verifier Artifact Format

```json
{
  "artifact_id": "V.001",
  "validator_id": "validator reference",
  "check_type": "structural/behavioral/semantic",
  "input_path": "artifacts/report.json",
  "expected": "PASS",
  "actual": "PASS",
  "verdict": "PASS",
  "evidence": ["file hash", "log excerpt"]
}
```

## Validators Applied

- `.agentic-pi/validators/validate_verifier_graph.py` — verifier artifact chain consistency

## Authority Boundaries

- Do NOT certify — only produce verifier evidence
- Do NOT write final_status.json or policy_decision.json
- Verifier artifacts feed into the policy engine — they are not the final word
