# v1.8 Domain Packs

```text
DOMAIN PACKS IMPLEMENTED
```

v1.8 adds deterministic domain packs for strategy planning. The purpose is to
stop pretending one generic planner handles every task type equally well.

domain packs can suggest, but domain packs cannot certify DONE.

The invariant is unchanged:

```text
Strategy can suggest.
Planner can select.
Milestones can guide.
Memory can suggest.
Domain packs can suggest.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

## Implemented Files

```text
.agentic-pi/domain_packs/coding.json
.agentic-pi/domain_packs/research.json
.agentic-pi/domain_packs/writing.json
.agentic-pi/domain_packs/debugging.json
.agentic-pi/domain_packs/experiment.json
.agentic-pi/domain_packs/benchmark.json
.agentic-pi/domain_packs/devops.json

.agentic-pi/runtime/domain_pack_selector.py

.agentic-pi/schemas/domain_pack.schema.json
.agentic-pi/schemas/domain_pack_selection.schema.json

tests/test_domain_packs.py
```

## Runtime Path

```text
goal_contract.json
  -> task_type_decision.json
  -> domain_pack_selection.json
  -> strategy_candidates.json
  -> applicability gate
  -> advisory experience retrieval
  -> strategy scores
  -> selected strategy
  -> certifier
```

`strategy_generator.py` uses a selected domain pack to enrich strategy
candidates with:

```text
common capabilities
verifier requirements
risk rules
```

It does not add final status authority.

## Domain Packs

Current packs:

```text
coding
research
writing
debugging
experiment
benchmark
devops
```

Each pack defines:

```text
allowed task types
allowed strategies
common capabilities
expected artifacts
evidence types
verifier requirements
risk rules
done-policy hints
```

Each pack also explicitly records:

```text
final_status_authority = certifier_only
can_certify_done = false
```

## Unknown Goals

Unknown goals do not guess unsafe packs.

If the task type is unknown, `domain_pack_selector.py` writes:

```text
selection_status = NEED_USER_DOMAIN
selected_domain_pack = ""
```

The strategy planner can still emit `S.UNKNOWN_NEED_USER`, but that strategy is
not executable and cannot produce a final certification status.

## Safety Boundary

Domain packs can suggest:

```text
which strategy ids are allowed
which evidence types matter
which risks should be surfaced
which verifier requirements should be attached
```

Domain packs cannot:

```text
write final_status.md
write certification.json
write policy_decision.json
write verifier_artifacts/
certify DONE
override retrieved experience safety
override strategy applicability gates
override policy_engine.py
override certify_run.py
```

## What v1.8 Proves

```text
coding goals load the coding pack
research goals load the research pack
benchmark goals load the benchmark pack
unknown goals do not guess unsafe packs
domain packs affect strategy candidates
domain packs cannot certify DONE
the v1.7 experience-memory path still works
```

## What v1.8 Does Not Prove

```text
domain packs are semantically optimal
domain packs cover every real-world task
strategy search is implemented
workflow optimization is implemented
full autonomous Pi chain runtime is safe
domain packs can certify final status
```

## Proof Commands

```cmd
python tests\test_domain_packs.py -v
python tests\test_strategy_planner.py -v
python -m unittest discover tests -v
```

For Pi smoke:

```cmd
pi --tools bash -p "Run exactly one bash command: python tests/test_domain_packs.py -v. Do not certify DONE yourself. Final status comes only from certify_run.py."
```

## Next

Next milestone:

```text
v1.9 = Strategy Search / Workflow Optimization
```

v1.9 should use trajectory metrics, drift evidence, advisory experience memory,
and domain-pack hints to compare workflow candidates. It still must not bypass
the certifier.
