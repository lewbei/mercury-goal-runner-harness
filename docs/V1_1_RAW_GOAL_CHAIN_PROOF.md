# v1.1 Raw Goal Chain Proof

This document records the v1.1 raw-goal proof boundary.

The goal is to prove a narrow path:

```text
raw goal -> goal_contract.json -> full harness run -> certifier status
```

This is not a claim of arbitrary natural-language autonomy.

## Status

```text
RAW GOAL CHAIN PROOF IMPLEMENTED
```

## Command

The deterministic compiler is:

```cmd
python .agentic-pi\runtime\pi_cli.py goal-compile <run_id> --goal "Create README.md explaining the harness" --mode legacy
```

Supported proof modes:

```text
legacy -> DONE_PASS
p2 -> CERTIFIED_DONE
missing_verifier -> NOT_DONE
```

## What It Proves

It proves that the harness can start from a raw goal string in deterministic
fixture mode, create a goal contract, run the full prepared harness path, and
let `certify_run.py` / `policy_engine.py` decide final status.

## What It Does Not Prove

It does not prove:

```text
general natural-language goal compilation
full autonomous Pi goal-runner.chain.md execution
live Mercury planning quality
automatic verifier generation
```

## Safe Claim

Safe claim:

```text
Pi can invoke a deterministic raw-goal compiler and then run the full harness
path on disposable raw-goal proof fixtures.
```

Unsafe claim:

```text
Pi can safely solve arbitrary raw goals autonomously.
```

That remains false.

## Proof Commands

```cmd
python tests\test_raw_goal_chain.py -v
python -m unittest discover tests -v
```
