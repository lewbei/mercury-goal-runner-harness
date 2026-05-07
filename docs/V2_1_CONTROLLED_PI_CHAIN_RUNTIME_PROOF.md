# v2.1 Controlled Pi Chain Runtime Proof

```text
CONTROLLED PI CHAIN RUNTIME PROOF IMPLEMENTED
```

v2.1 adds a bounded live Pi smoke runner for the existing Pi chain contract.
It does not claim broad autonomous `goal-runner.chain.md` runtime.

The invariant is unchanged:

```text
Who is allowed to certify DONE?
Pi can orchestrate.
Mercury can compile / execute / report.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

## Implemented Files

```text
.agentic-pi/runtime/run_pi_chain_smoke.py
.agentic-pi/schemas/pi_chain_runtime_result.schema.json
tests/test_pi_chain_runtime_proof.py
docs/V2_1_CONTROLLED_PI_CHAIN_RUNTIME_PROOF.md
```

## Controlled Chain

The controlled chain has three Pi steps:

```text
verifier-generator -> verifier-reviewer -> goal-orchestrator
```

The first two steps are read-only. The final step may run only the deterministic
certifier command on a disposable `pi_smoke_*` run:

```cmd
python .agentic-pi/validators/certify_run.py .agentic-runs/<run_id>
```

The runner reads the status artifacts directly after Pi exits:

```text
final_status.md
certification.json
policy_decision.json
```

## Commands

Dry-run contract proof:

```cmd
python .agentic-pi\runtime\run_pi_chain_smoke.py --target-run-id pi_smoke_chain_p2_strong
```

Live Pi smoke:

```cmd
python .agentic-pi\runtime\run_pi_chain_smoke.py --live --clean --target-run-id pi_smoke_chain_p2_strong
```

Output:

```text
.agentic-runs/pi_chain_smoke_outputs/pi_chain_runtime_result.json
```

## Local Live Smoke Evidence

The live smoke was run locally with:

```cmd
cmd /c python .agentic-pi\runtime\run_pi_chain_smoke.py --live --clean --target-run-id pi_smoke_chain_p2_strong
```

Observed direct artifact status values:

```text
final_status.md = CERTIFIED_DONE
certification.json = CERTIFIED_DONE
policy_decision.json = CERTIFIED_DONE
status_artifacts_agree = true
result_status = PASS
can_certify_done = false
```

This is local runtime evidence. It is not automated CI evidence, and it is not
a strict internal Pi tool-call audit.

## Safe Claim

Safe claim:

```text
Pi can execute a bounded verifier-generator -> verifier-reviewer ->
goal-orchestrator smoke on a disposable P2 run, and final status is read from
certifier-owned artifacts.
```

Unsafe claim:

```text
The full Pi goal-runner chain is autonomously verified for arbitrary goals.
```

That remains false.

## What v2.1 Proves

```text
controlled Pi prompts can be generated deterministically
Pi is invoked without globally installed extensions in the smoke runner
first two Pi steps are read-only
goal-orchestrator is restricted to the certifier command
the result schema records final_status_authority = certifier_only
the result schema records can_certify_done = false
```

## What v2.1 Does Not Prove

```text
arbitrary natural-language goal autonomy
live worker execution through the full chain
semantic quality of verifier proposals
strict internal Pi tool-call audit for the live process
global Pi extension compatibility
```

## Proof Commands

```cmd
python tests\test_pi_chain_runtime_proof.py -v
python .agentic-pi\runtime\run_pi_chain_smoke.py --target-run-id pi_smoke_chain_p2_strong
```
