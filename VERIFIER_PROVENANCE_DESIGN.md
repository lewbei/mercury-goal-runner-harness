# Verifier Provenance Design

Owner: Mercury Goal Runner Harness
Status: source-of-truth
Last verified: 2026-05-06

## Direction

Research direction:

```text
Verifier-Provenance Goal Runner Harness
```

Research-style name:

```text
Oracle-Governed Agent Harness for Goal Certification
```

The system should allow Mercury V2 to work fast, while final completion is controlled by verifier provenance.

## Verifier Authority Levels

```text
P0 = self-authored verifier
     Same Worker/run created the solution and verifier.
     Advisory only.

P1 = local public verifier
     Existing repo tests or visible benchmark tests.
     Can gate progress, but normally not enough for final certification.

P2 = independent audited verifier
     Separate verifier agent, separate model/run, pre-implementation test,
     human-reviewed test, differential test, or metamorphic test.
     Can certify with corroboration.

P3 = authoritative hidden verifier
     Hidden tests, user-provided final test, independent benchmark oracle,
     or human sign-off.
     Highest authority.
```

Main policy:

```text
P0 alone cannot certify DONE.
```

## New Status Meanings

These statuses are wired into `certify_run.py` only for provenance-mode runs. A run enters provenance mode when it contains `verifier_contract.json`.

```text
NOT_DONE
  Required artifact or required verifier evidence is missing.

PROVISIONAL_DONE
  Artifact exists and some tests/evidence pass, but verifier authority is too weak.

CERTIFIED_DONE
  Required artifacts exist and verifier evidence has sufficient authority.

BLOCKED
  The harness cannot continue without an external dependency or missing prerequisite.

NEED_USER
  The harness needs user judgment, user-provided tests, or clarification.
```

Current runtime compatibility:

```text
Runs without verifier_contract.json still emit DONE_PASS / DONE_FAIL / BLOCKED / NEED_USER.
```

## Verifier Artifact Model

Every verifier/test/evidence artifact should record:

```text
who created it
when it was created
whether it was created before or after the solution
whether the same Worker created it
whether it is independent from the solution
whether it executes behavior
whether it is strong enough to certify DONE
```

The first schema is:

```text
.agentic-pi/schemas/verifier_artifact.schema.json
```

For local schema-validator compatibility, `mock_ratio_percent` is stored as an integer percentage instead of a floating-point ratio.

## Verifier Contract Model

Every run should eventually have a verifier contract that states what kind of verifier is required before final DONE:

```text
.agentic-pi/schemas/verifier_contract.schema.json
```

The verifier contract defines required authority level, required behaviors, forbidden verifier patterns, and whether self-generated-only verification is allowed.

Important policy-engine validation that the current JSON schema validator cannot express:

```text
If required_verifier_level is P2 or P3, allow_self_generated_only must be false.
```

That rule belongs in the later deterministic policy engine, not in this docs-and-schema slice.

## Policy Draft

Static policy config:

```text
certification_policy.yaml
```

This config is declarative only for this slice. It is not yet consumed by the certifier.

The current certifier implements the first hard rule directly:

```text
P0 alone cannot certify DONE.
```

It does not yet implement the full smell scanner, strength scorer, or policy engine.

## Relationship To v0.3 PlanGraph

The current v0.3 Artifact-Linked PlanGraph remains useful because it tracks exact artifact handoffs:

```text
T1 produces A.SOURCE
T2 requires A.SOURCE
```

But PlanGraph is no longer the main novelty direction. The next novelty direction is:

```text
verifier provenance governance
```

PlanGraph says what artifact was handed off. Verifier provenance says who is allowed to certify that the handoff and behavior are enough for DONE.

## Deferred

Do not build these in this slice:

- smell scanner,
- strength scorer,
- full policy engine backed by certification_policy.yaml,
- Pi integration,
- diagnostic task suite,
- benchmark expansion,
- memory behavior,
- or more PlanGraph features.
