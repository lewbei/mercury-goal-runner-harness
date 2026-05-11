---
name: harness-tdd
description: Run test-driven validation — execute the implementation's test suite and capture results as verifier evidence. BEHAVIORAL_ORACLE check, not certification.
---

# Harness TDD Skill

**Phase:** VALIDATING
**Role:** Critic
**Artifact:** `test_outputs/` directory + verifier evidence

## Purpose

Run test-driven validation: execute the implementation's test suite and capture results as verifier evidence. This is a BEHAVIORAL_ORACLE check.

## Process

1. Identify the test command from the plan or goal contract
2. Execute the test command in the controlled workspace
3. Capture stdout, stderr, exit code
4. Write test output to `test_outputs/<test_name>.json`
5. Create a verifier artifact recording the result

## Output

```json
{
  "test_name": "pytest test_report.py",
  "exit_code": 0,
  "passed": 10,
  "failed": 0,
  "output_summary": "All tests passed",
  "verdict": "PASS"
}
```

## Authority Boundaries

- Do NOT modify test code — run what exists
- Do NOT certify — only produce evidence
- Do NOT write authority files: final_status.json, certification.json, policy_decision.json
