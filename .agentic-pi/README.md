# .agentic-pi Structure

Status: source-of-truth ownership map.

This folder contains the local deterministic harness. It is not the external
`pi` CLI. The real Pi agent is launched from `cmd` by typing:

```cmd
pi
```

Core invariant:

```text
Who is allowed to certify DONE?
Pi can orchestrate.
Mercury can compile / execute / report.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

## Ownership Map

```text
.agentic-pi/
  benchmark/      small local benchmark runner and fixtures
  diagnostics/    deterministic diagnostic and smoke fixtures
  domain_packs/   task-domain hints; advisory only
  evaluation/     trajectory/tool-use scoring helpers
  examples/       frozen sample run inputs
  memory/         append-only learning records; advisory only
  prompts/        prompt files for controlled Pi/Mercury probes
  proof_matrix/   bounded proof claim registry
  runtime/        local deterministic harness tools and runners
  schemas/        JSON schemas for run artifacts and reports
  security/       safety and protected-surface notes
  skills/         local skill/prompt support material
  validators/     schema validation, certifier, policy engine, verifier checks
```

## Authority Boundary

The following folders can produce evidence, reports, plans, traces, or advisory
signals:

```text
diagnostics/
domain_packs/
evaluation/
memory/
prompts/
proof_matrix/
runtime/
```

They cannot certify DONE.

Final status remains owned by:

```text
validators/certify_run.py
runtime/policy_engine.py
```

## Cleanup Boundary

This map intentionally does not move existing runtime modules yet. The current
runtime code is import-path sensitive because many tools are executed directly
as scripts. Future physical refactors should add entrypoint tests before moving
files into subpackages.
