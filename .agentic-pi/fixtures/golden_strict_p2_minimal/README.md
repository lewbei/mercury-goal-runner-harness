# golden_strict_p2_minimal

Canonical strict P2 fixture source for CI-backed reproducibility.

`run_template/` contains the pre-existing strict-path proof and worker artifacts.
It intentionally does **not** contain certifier-owned final authority artifacts:

- `certification.json`
- `final_status.json`
- `final_status.md`
- `policy_decision.json`

Materialize the canonical run folder with:

```bash
python .agentic-pi/fixtures/golden_strict_p2_minimal/materialize.py
```

The materializer writes `.agentic-runs/golden_strict_p2_minimal/`, then prepares
non-final derived evidence required by the current strict runner:

- `run_manifest.json` and `audit_report.json` via `audit_run.py`
- `validator_certification.json` via `validator_factory.py`

Final status still comes only from `certify_run.py` through `full_verify.py`.
