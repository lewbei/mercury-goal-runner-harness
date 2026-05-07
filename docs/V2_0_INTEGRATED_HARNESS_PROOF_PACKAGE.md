# v2.0 Integrated Harness Proof Package

```text
INTEGRATED HARNESS PROOF PACKAGE IMPLEMENTED
```

v2.0 packages the current deterministic proof layers into one inspectable proof
matrix. It does not add full autonomous Pi runtime.

The invariant is unchanged:

```text
Who is allowed to certify DONE?
Strategy can suggest.
Planner can select.
Milestones can guide.
Drift reports can block.
Trajectory evaluators can fail unsafe tool use.
Memory can suggest.
Domain packs can suggest.
Workflow search can rank.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

## Implemented Files

```text
.agentic-pi/proof_matrix/proof_matrix.json
.agentic-pi/runtime/run_proof_matrix.py
.agentic-pi/schemas/proof_matrix.schema.json
.agentic-pi/schemas/proof_matrix_result.schema.json
docs/V2_0_EXAMPLES.md
tests/test_v2_proof_package.py
```

## Proof Matrix

The matrix maps claims to:

```text
claim id
claim text
mode = quick or full
command
expected evidence
claim boundary
```

Quick mode runs bounded proof commands and writes output only under:

```text
.agentic-runs/proof_matrix_outputs/
```

Full mode includes heavier local commands such as the complete unit suite and
benchmark. Full mode can take longer and can refresh generated reports, so it is
not used as the default test fixture.

## One-Command Runner

Quick proof:

```cmd
python .agentic-pi\runtime\run_proof_matrix.py --mode quick
```

Full proof:

```cmd
python .agentic-pi\runtime\run_proof_matrix.py --mode full
```

Output:

```text
.agentic-runs/proof_matrix_outputs/proof_matrix_result.json
```

The proof matrix result records:

```text
all_passed
entry_count
passed_count
failed_count
stdout_tail for each command
final_status_authority = certifier_only
can_certify_done = false
```

## Example Set

The v2.0 example index is:

```text
docs/V2_0_EXAMPLES.md
```

It includes:

```text
DONE_PASS
PROVISIONAL_DONE
CERTIFIED_DONE
NOT_DONE
drift detected
trajectory failure
memory suggestion
domain pack selection
workflow search
```

## Safe Claim

Safe claim:

```text
The harness has an integrated local proof matrix for the deterministic layers
implemented through v2.0.
```

Unsafe claim:

```text
The full Pi goal-runner chain is autonomously verified.
```

That remains false.

## What v2.0 Proves

```text
proof matrix schema validates
quick proof runner executes bounded proof commands
proof_matrix_result.json records pass/fail evidence
proof matrix cannot certify DONE
examples cover the main status and safety cases
tested and untested behavior remain separated
```

## What v2.0 Does Not Prove

```text
full autonomous Pi chain runtime
semantic optimality of plans, milestones, memory, domains, or workflows
external coding-agent host integration beyond local fixtures
large benchmark validity
paper-ready experimental claims
```

## Proof Commands

```cmd
python tests\test_v2_proof_package.py -v
python .agentic-pi\runtime\run_proof_matrix.py --mode quick
python -m unittest discover tests -v
```
