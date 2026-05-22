# Certifier Golden Behavior Lock v1

Status: pre-refactor behavior lock. This milestone adds deterministic tests only. It does not modularize `certify_run.py`, does not move certifier code, and does not add a new status writer.

## Purpose

Before the certifier monolith is split, freeze the current authority behavior with golden tests. The tests are bounded regression evidence, not a proof that arbitrary future goals are safe.

## Locked behavior cases

The lock covers these current behaviors:

```text
missing verifier artifact -> NOT_DONE
P0 verifier evidence -> PROVISIONAL_DONE
P1 verifier evidence -> PROVISIONAL_DONE
P2 strong verifier evidence -> CERTIFIED_DONE
P2 weak verifier evidence -> PROVISIONAL_DONE
policy says CERTIFIED_DONE but replay gate fails -> final NOT_DONE from certification.json
artifact test allowlist rejects shell operators, Python -c/-m, path escapes, protected artifact arguments, and unknown executables
worker-reported protected status/provenance paths block certification
legacy pass -> DONE_PASS (deprecated compatibility only)
legacy fail -> DONE_FAIL (deprecated compatibility only)
final_status.md cannot upgrade final_status.json authority
```

## Boundary

```text
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

This lock intentionally preserves legacy compatibility behavior until a separate fail-closed migration is planned and validated. It is a prerequisite for later certifier modularization, not the modularization itself.

## Validation

Focused command:

```cmd
python tests\test_certifier_golden_behavior_lock.py -v
```

Expected follow-up before any refactor claim:

```cmd
python .agentic-pi\runtime\run_proof_matrix.py --mode quick
python tests\test_repo_structure_cleanup.py -v
git diff --check
```
