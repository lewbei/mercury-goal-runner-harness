# Verifier-Provenance Problem and Gap

Owner: Mercury Goal Runner Harness
Status: source-of-truth
Last verified: 2026-05-06

## Core Question

Who is allowed to certify DONE?

This is now the central system question. The project should not be framed mainly as another agent harness, another planner, or another evaluator loop. The sharper direction is verifier provenance governance: deciding which verifier artifacts are allowed to certify final completion.

## Problem

An agent can create the artifact, create the test, pass the test, and still be wrong.

That means the core failure is not only weak testing. The deeper failure is self-certified completion. A goal-running harness needs a runtime policy that records where verifier evidence came from, when it was created, whether it is independent from the solution, and whether it has enough authority to certify DONE.

## Gap

Existing work studies corrupt success, weak tests, oracle generation, benchmark strengthening, graph planning, and evaluator loops. Those are relevant prior threats, but they do not fully answer the harness-level governance question:

```text
Which verifier artifacts are allowed to certify final DONE?
```

This repo should focus on that narrower gap:

```text
Prevent self-certified DONE.
```

## Conservative Claim

Do not claim:

```text
The harness fully solves verification.
```

Claim:

```text
We reduce self-certified false completion by separating advisory evidence from certifying evidence.
```

Main rule:

```text
Self-generated post-solution tests cannot certify DONE alone.
```

## First Research Target

The first research target should be coding-agent completion certification, not general AGI or all goal-running tasks.

Coding is the right first host domain because it has clear artifacts, executable tests, existing coding-agent harnesses, and known false-completion pressure. Future integration candidates include OpenHands, mini-SWE-agent, and SWE-bench-style evaluations, but this repo should cite those as future host targets or threat-model context until local measurements exist.

Primary references to review before paper claims:

- OpenHands: https://github.com/OpenHands/OpenHands
- mini-SWE-agent: https://github.com/SWE-agent/mini-swe-agent
- UTBoost / SWE-bench test-strength work: https://arxiv.org/abs/2506.09289

## Current Repo Boundary

Current implemented state:

```text
v0.3 Artifact-Linked PlanGraph local prototype
```

Next research direction:

```text
Verifier-Provenance Goal Runner Harness
```

The v0.3 PlanGraph layer remains useful for artifact handoffs, but it is no longer the main novelty direction. The next system layer should govern verifier provenance and certification authority.
