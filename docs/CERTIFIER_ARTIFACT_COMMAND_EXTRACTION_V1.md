# Certifier Artifact Command Extraction v1

Status: behavior-preserving helper extraction. This milestone moves only the artifact command-test helper surface out of `certify_run.py`.

## Extracted module

```text
.agentic-pi/validators/certifier_artifact_commands.py
```

The module owns:

```text
split_artifact_command
validate_artifact_command_allowlist
run_artifact_command_test
ALLOWED_ARTIFACT_COMMAND_EXECUTABLES
FORBIDDEN_ARTIFACT_COMMAND_CHARS
FORBIDDEN_ARTIFACT_COMMAND_TOKENS
```

## Boundary

This extraction intentionally does not move:

```text
log_artifact_test_verifier
verifier contract/artifact loading
policy engine invocation
post-policy gates
certification.json writing
final_status.json writing
final_status.md rendering
legacy DONE_PASS / DONE_FAIL mapping
```

Artifact command tests remain a narrow certifier-owned check surface:

```text
python <run-relative-script.py> [safe args]
```

The allowlist must continue to reject shell operators, Python `-c`/`-m`, path escapes, protected status artifact arguments, protected provenance script paths, absolute paths, and unknown executables.

## Validation

Focused command:

```cmd
python tests\test_certifier_artifact_command_extraction.py -v
```

Required companion checks:

```cmd
python tests\test_certifier_golden_behavior_lock.py -v
python tests\test_final_status_json_authority.py -v
python .agentic-pi\runtime\run_proof_matrix.py --mode quick
python tests\test_repo_structure_cleanup.py -v
git diff --check
```
