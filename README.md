# Mercury Goal Runner Harness

This harness controls Mercury V2 as a fast worker inside a verified goal-execution system.

The goal is not to make Mercury V2 magically smarter by looping. The goal is to place Mercury V2 inside a controlled harness where every goal becomes a contract, every step produces evidence, and final success is certified by deterministic checks.

## Current status

v0.3.6 is the Policy Engine on top of the v0.3.5 Strength Scorer.

The current research direction is:

```text
Verifier-Provenance Goal Runner Harness
```

The new core question is:

```text
Who is allowed to certify DONE?
```

The latest local benchmark report is:

```text
benchmark_outputs/benchmark_report.md
```

Current benchmark scoring checks the expected verdict for each goal, not just whether the model says `DONE_PASS`. The impossible goal is expected to fail honestly.

See [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for the proof summary and current limitations.
See [`PROBLEM_AND_GAP.md`](PROBLEM_AND_GAP.md) for the current research problem statement.
See [`VERIFIER_PROVENANCE_DESIGN.md`](VERIFIER_PROVENANCE_DESIGN.md) for the verifier provenance model.
See [`docs/V0_2_1_FREEZE.md`](docs/V0_2_1_FREEZE.md) for the exact freeze boundary.
See [`docs/V0_3_PLANGRAPH.md`](docs/V0_3_PLANGRAPH.md) for the PlanGraph prototype boundary.
See [`docs/V0_3_2_PROVENANCE_GATE_FREEZE.md`](docs/V0_3_2_PROVENANCE_GATE_FREEZE.md) for the provenance runtime gate boundary.
See [`docs/V0_3_3_PROVENANCE_GATE_DIAGNOSTICS.md`](docs/V0_3_3_PROVENANCE_GATE_DIAGNOSTICS.md) for the provenance diagnostic fixture boundary.
See [`docs/V0_3_4_SMELL_SCANNER.md`](docs/V0_3_4_SMELL_SCANNER.md) for the metadata-level verifier smell scanner boundary.
See [`docs/V0_3_5_STRENGTH_SCORER.md`](docs/V0_3_5_STRENGTH_SCORER.md) for the verifier strength scoring boundary.
See [`docs/V0_3_6_POLICY_ENGINE.md`](docs/V0_3_6_POLICY_ENGINE.md) for the deterministic policy engine boundary.

The current proof path is:

```text
python -m unittest discover tests -v
python .agentic-pi\benchmark\run_benchmark.py
```

It demonstrates:

1. a Goal Contract was created,
2. the planner writes plans only,
3. the Guarded Worker writes artifacts inside the active run folder,
4. false pass evidence is rejected,
5. final output paths must match the contract exactly,
6. `artifact_tests` run executable checks for behavior claims,
7. `plan_graph.json`, `artifact_registry.json`, and `task_graph.json` are generated for normal runs,
8. downstream tasks require exact artifact IDs from upstream tasks,
9. provenance-mode runs can return `NOT_DONE`, `PROVISIONAL_DONE`, or `CERTIFIED_DONE`,
10. the four-case provenance diagnostic set verifies P0/P1/P2/missing-verifier behavior,
11. verifier smell reports are recorded without changing final status yet,
12. verifier strength reports are recorded,
13. `policy_decision.json` decides provenance-mode final status,
14. and the benchmark reports false-PASS status explicitly.

## Core parts

1. Prompt Compiler  
Converts a rough user goal into a structured Goal Contract.

2. Goal Contract  
Defines the cleaned goal, final outputs, constraints, done criteria, and failure criteria.

3. Guarded Worker  
Executes one approved step at a time and reports evidence.

4. Trace Logger  
Records what happened during the run.

5. Certifier  
Checks evidence, required files, logs, done criteria, artifact tests, PlanGraph links, and verifier provenance before certification. Legacy runs without `verifier_contract.json` still use `DONE_PASS` / `DONE_FAIL`.

6. Artifact-Linked PlanGraph
Links task outputs to exact artifact IDs and validates downstream artifact consumption when graph files exist.

7. Verifier Provenance Gate
When `verifier_contract.json` exists, separates weak/self-generated evidence from certifying evidence.

8. Smell Scanner
Records metadata-level verifier smell reports for strength scoring and later policy enforcement.

9. Strength Scorer
Scores verifier strength as `weak`, `advisory`, `gating`, or `certifying` for later policy enforcement.

10. Policy Engine
Consumes verifier artifacts, smell reports, strength reports, and the verifier contract to decide provenance-mode status.

## Core rule

Mercury may propose, plan, execute, and report, but it cannot certify final success.

Evidence beats confidence.

Next provenance rule:

```text
Self-generated post-solution tests cannot certify DONE alone.
```

## Quick validation commands

Validate a Goal Contract:

```cmd
python .agentic-pi\validators\validate_schema.py .agentic-pi\schemas\goal_contract.schema.json .agentic-runs\real_goal_001\goal_contract.json
```

Validate a Worker step log:

```cmd
python .agentic-pi\validators\validate_schema.py .agentic-pi\schemas\step_result.schema.json .agentic-runs\real_goal_001\step_logs\001.json
```

Run certification:

```cmd
python .agentic-pi\validators\certify_run.py .agentic-runs\<run_id>
```

Run the deterministic smoke test:

```cmd
python smoke_v01.py
```

## Artifact tests

Run the artifact and harness regression tests:

```cmd
python -m unittest discover tests -v
```

## Next milestone

The first provenance runtime gate is implemented:

```text
verifier_artifact.schema.json
verifier_contract.schema.json
certification_policy.yaml
verifier_provenance.py
```

The v0.3.3 diagnostic set lives at:

```text
.agentic-pi/diagnostics/provenance_gate/
```

Each v0.3.3 case is a copy-ready run fixture. The regression test copies it into `.agentic-runs/test_<case_name>/`, runs the certifier, and reads `final_status.md`.

The certification policy engine is implemented for the current provenance mode. Full oracle governance, Pi integration, and larger diagnostic evaluation remain deferred.

## Planner Stub

The current `plan_router.py` is a deterministic stub for testing. See [PLAN_ROUTER.md](PLAN_ROUTER.md) for details. Real planner agents will replace this stub in future versions.
