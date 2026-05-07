# Diagnostics Folder

Status: deterministic proof fixture map.

Diagnostics are small controlled checks. They are not broad benchmarks and they
do not certify DONE by themselves.

Final status comes only from `certify_run.py` and `policy_engine.py`.

## Active Groups

```text
evaluation/             v0.4 certification-mode comparison
host_integration/       v0.6 local host-task checks
pi_command_discipline/  v0.5.9 command audit fixtures
pi_direct_behavior/     v2.2 Pi/Mercury behavior fixtures
pi_real_interactive/    v2.3-v2.6 captured real Pi evidence and transcripts
provenance_gate/        v0.3.3 P0/P1/P2/missing-verifier fixtures
trajectory_evaluation/  v1.6 tool-use trajectory fixtures
```

## Diagnostic Rule

Diagnostics can show:

```text
PASS / FAIL for a bounded claim
false CERTIFIED_DONE rate on a small fixture set
unsafe trajectory behavior
status-upgrade attempts
```

Diagnostics cannot show:

```text
arbitrary Pi autonomy is safe
Mercury semantic planning quality is solved
unbounded bash is safe
DONE is certified by the model
```
