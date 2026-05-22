# Certifier IO/Path Helper Extraction v1

Status: behavior-preserving helper extraction. This milestone moves only pure helper code out of `certify_run.py`.

## Extracted modules

```text
.agentic-pi/validators/certifier_io.py
.agentic-pi/validators/certifier_paths.py
```

`certifier_io.py` owns:

```text
load_json
sha256_file
write_json
load_local_module
schema_path
validate_with_schema
```

`certifier_paths.py` owns:

```text
PROTECTED_NAMES
PROTECTED_PREFIXES
resolve_run_path
run_relative
output_candidates
find_output
non_empty_string_list
```

## Boundary

This extraction does not change the policy/certifier authority chain. It does not move verifier loading, policy invocation, post-policy gates, certification assembly, result JSON writing, markdown rendering, or legacy compatibility logic.

The certifier runner imports these helpers and keeps the same result-writing flow. Golden behavior tests remain the authority-preserving regression evidence.

## Validation

Focused command:

```cmd
python tests\test_certifier_io_paths_extraction.py -v
```

Required companion checks:

```cmd
python tests\test_certifier_golden_behavior_lock.py -v
python tests\test_final_status_json_authority.py -v
python .agentic-pi\runtime\run_proof_matrix.py --mode quick
python tests\test_repo_structure_cleanup.py -v
git diff --check
```
