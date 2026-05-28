# Certifier Modularization Pre-Audit v1

Status: pre-refactor audit only. This file does not certify DONE and does not implement modularization.

## Authority invariant

```text
Pi can orchestrate.
Mercury can compile / execute / report.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

Protected status artifacts remain owned by the certifier/policy path:

```text
policy_decision.json
certification.json
final_status.json
final_status.md
```

Do not create a second writer for these artifacts during modularization. The next implementation milestone must preserve byte/semantic behavior before any module split is allowed to claim success.

## Scope of this audit

This audit maps the current certifier monolith and defines future seams. It does not execute, certify, or change final status artifacts. It intentionally does not:

- move code out of `.agentic-pi/validators/certify_run.py`,
- change status semantics,
- change legacy compatibility behavior,
- change policy decisions,
- change final-status rendering,
- add a new authority path.

## Current certifier responsibility map

Primary file:

```text
.agentic-pi/validators/certify_run.py
```

Current responsibility clusters:

| Cluster | Current functions / surface | Responsibility | Authority risk |
| --- | --- | --- | --- |
| Shared certifier utilities | `load_json`, `sha256_file`, `write_json`, `load_local_module`, `schema_path`, `validate_with_schema` | JSON IO, hashing, local validator loading, schema validation | Utility extraction must not make protected artifact writes available to workers. |
| Status coercion and final-status data | `status_after_failures`, `build_final_status_data` | Convert failed provenance runs to `NOT_DONE`, failed legacy runs to `DONE_FAIL`, and build final status JSON fields | Any drift can create false DONE or wrong `status_source`. |
| Run path safety | `resolve_run_path`, `run_relative`, `output_candidates`, `find_output`, `validate_touched_files` | Confine run-relative paths and reject protected status/provenance paths | Duplicate path logic can create bypasses. Keep one canonical implementation. |
| Step/run structure validation | `validate_step_shape`, `load_merged_steps`, `validate_against_merged_plan`, `run_plan_graph_validation` | Validate step logs, touched files, merged-plan agreement, and plan graph | A refactor must not let execution evidence skip structural checks. |
| Artifact command allowlist | `split_artifact_command`, `validate_artifact_command_allowlist`, `run_artifact_command_test` | Execute only allowed run-relative Python artifact tests from `goal_contract.json` | This is a high-risk command surface; preserve fail-closed behavior. |
| Verifier artifact logging | `artifact_test_assertion_count`, `safe_verifier_id`, `log_artifact_test_verifier` | Convert passing artifact tests into controlled verifier artifacts in provenance mode | Must not let self-generated tests become stronger than policy permits. |
| Verifier/provenance pipeline | `load_verifier_contract`, `load_verifier_artifacts`, `record_verifier_smell_reports`, `record_verifier_strength_reports`, `check_contract_target_artifacts`, `artifact_is_certifying_for_contract`, `decide_provenance_status`, `run_policy_engine` | Load provenance inputs, record smell/strength evidence, and invoke policy engine | Policy decides; certifier must not silently override policy to DONE. |
| Post-policy gates | `apply_artifact_location_gate`, `apply_replay_gate`, `apply_audit_report_gate`, `apply_drift_report_gate`, `apply_evidence_freeze_gate`, `apply_memory_authority_gate`, `apply_formal_verification_gate`, `apply_cryptographic_signature_gate`, `check_validator_certification` | Downgrade status when deterministic gates fail after policy decision | Preserve post-policy downgrade semantics and `status_source: certification.json` on blocking outcomes. |
| Done criteria and output checks | `evaluate_done_criteria`, `run_python_output` | Legacy/output compatibility checks and Python output/import checks | Legacy is deprecated compatibility-only; do not expand it into the current authority path. |
| Final authority write/render | `main`, `build_final_status_data`, `validate_final_status.py`, `final_status_renderer.py` | Write `certification.json`, write `final_status.json`, validate, rewrite after validation, render derived markdown | Two-pass write is subtle; modularization must not leave stale or inconsistent status artifacts. |

Policy file kept separate:

```text
.agentic-pi/runtime/policy_engine.py
```

Policy responsibilities:

- `decide_run_policy` decides `NOT_DONE`, `PROVISIONAL_DONE`, or `CERTIFIED_DONE` from verifier contract/artifacts and hard failures.
- `write_policy_decision` writes `policy_decision.json`.
- The policy engine does not write `certification.json`, `final_status.json`, or `final_status.md`.

## Authority risks to preserve during future refactor

1. **Policy/final-status ordering**: policy can return `CERTIFIED_DONE`, then later certifier gates can block. Final status must become `NOT_DONE` for provenance mode and cite `certification.json` as the source when later failures exist.
2. **Two-pass final-status write**: current certifier writes status artifacts, validates them, appends validation failures if needed, then rewrites final artifacts. A split must keep final artifacts consistent after validation.
3. **Markdown is derived only**: `final_status.md` must never upgrade `final_status.json`.
4. **Protected path checks are authority barriers**: `certification.json`, `final_status.json`, `final_status.md`, `policy_decision.json`, `trace.jsonl`, `verifier_artifacts/`, `verifier_smell_reports/`, and `verifier_strength_reports/` stay protected from worker evidence.
5. **Artifact command execution is high risk**: keep the allowlist to run-relative Python scripts, no shell operators, no Python eval/module shortcuts, no path escapes, no protected status artifact arguments.
6. **Legacy/provenance status mapping**: provenance failures become `NOT_DONE`; deprecated legacy failures become `DONE_FAIL`; deprecated legacy success remains `DONE_PASS` only for compatibility coverage until a separate fail-closed migration changes it.
7. **Policy decides; certifier writes final status**: no future module may both make policy decisions and write final status unless it is still explicitly part of the certifier-owned path and tested as such.

## Proposed future module seams

These are future seams only. They are not implemented by this audit.

```text
.agentic-pi/validators/certifier_io.py             [DONE]
.agentic-pi/validators/certifier_paths.py           [DONE]
.agentic-pi/validators/certifier_step_logs.py       [PLANNED - not yet implemented]
.agentic-pi/validators/certifier_artifact_commands.py [DONE]
.agentic-pi/validators/certifier_goal_outputs.py    [PLANNED - not yet implemented]
.agentic-pi/validators/certifier_verifier_pipeline.py [PLANNED - not yet implemented]
.agentic-pi/validators/certifier_gates.py           [DONE]
.agentic-pi/validators/certifier_final_status.py    [PLANNED - not yet implemented]
```

Suggested seam contract:

| Future seam | Owns | Must not own |
| --- | --- | --- |
| `certifier_io.py` | JSON IO, hashing, schema validation helpers | Policy decisions or final status semantics |
| `certifier_paths.py` | Run-relative path resolution, protected path constants, output lookup | Command execution |
| `certifier_step_logs.py` | Step shape, touched files, merged-plan and plan-graph checks | Status writing |
| `certifier_artifact_commands.py` | Command splitting, allowlist, command artifact tests, controlled verifier log helper | Shell execution beyond allowlist |
| `certifier_goal_outputs.py` | Final output existence/hash checks, done criteria, Python script/import checks | Provenance policy decisions |
| `certifier_verifier_pipeline.py` | Verifier contract/artifact loading, smell/strength report recording, target checks | Final status writing |
| `certifier_gates/` | One post-policy gate per module with a common fail-closed interface | Policy status upgrade |
| `certifier_final_status.py` | `status_after_failures`, final certification object assembly, final-status JSON data, validation/render orchestration | Verifier artifact mutation |

Common gate interface for future modules:

```python
def apply_gate(run_dir, provenance_mode, failed, passed, current_status):
    """Return the status after this gate. Append deterministic evidence to passed/failed."""
```

## Required golden behavior before any refactor

Before moving code, create or identify golden fixtures that prove the current monolith behavior. Required cases:

```text
missing verifier artifact -> NOT_DONE
P0 verifier evidence -> PROVISIONAL_DONE
P1 verifier evidence -> PROVISIONAL_DONE
P2 strong verifier evidence -> CERTIFIED_DONE
P2 weak or smelly verifier evidence -> PROVISIONAL_DONE or NOT_DONE according to existing policy
legacy pass -> DONE_PASS (deprecated compatibility only)
legacy fail -> DONE_FAIL (deprecated compatibility only)
policy CERTIFIED_DONE plus later replay/evidence/audit gate failure -> final NOT_DONE with status_source certification.json
artifact command shell/operator/eval/path-escape/protected-argument attempt -> blocked
worker-touched verifier_artifacts or protected status path -> blocked
final_status.md says CERTIFIED_DONE while final_status.json says NOT_DONE -> authoritative status remains NOT_DONE
```

Existing high-value tests that must stay green:

```text
tests/test_final_status_json_authority.py
tests/test_verifier_provenance_runtime.py
tests/test_raw_goal_chain.py
tests/test_runtime_enforcement.py
tests/test_replay_certification.py
tests/test_smell_scanner.py
tests/test_strength_scorer.py
tests/test_policy_engine.py
tests/test_provenance_gate.py
```

Recommended future refactor validation command set:

```cmd
python tests\test_final_status_json_authority.py -v
python tests\test_verifier_provenance_runtime.py -v
python tests\test_raw_goal_chain.py -v
python tests\test_runtime_enforcement.py -v
python tests\test_replay_certification.py -v
python tests\test_policy_engine.py -v
python tests\test_provenance_gate.py -v
python .agentic-pi\runtime\run_proof_matrix.py --mode quick
python tests\test_repo_structure_cleanup.py -v
git diff --check
git status -sb
```

## Stepwise future implementation plan

1. Add golden behavior snapshots for the cases above while `certify_run.py` remains monolithic.
2. Extract pure helpers first (`certifier_io.py`, then `certifier_paths.py`) with no behavior change.
3. Extract artifact command allowlist as a high-risk seam only after command allowlist tests are green.
4. Extract post-policy gates one at a time using the common gate interface.
5. Extract final-status writer last, after all downgrade and markdown-derived-only tests are locked.
6. Only after the final-status writer extraction passes golden tests may the project claim certifier modularization behavior preservation.

## Current decision

Proceed next with golden certifier behavior tests, not code movement. The certifier modularization pre-audit is complete when this document and its lock test pass. The actual modularization remains a later milestone.
