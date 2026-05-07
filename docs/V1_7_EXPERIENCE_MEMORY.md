# v1.7 Experience Memory

```text
EXPERIENCE MEMORY IMPLEMENTED
```

v1.7 adds safe self-improvement through reusable strategy lessons. It records
what worked, what failed, what was provisional, and why. It does not let memory
rewrite the harness or certify DONE.

Core invariant:

```text
Who is allowed to certify DONE?
Strategy can suggest.
Planner can select.
Milestones can guide.
Drift reports can block.
Trajectory evaluators can fail unsafe tool use.
Memory can suggest.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

## Added Files

```text
.agentic-pi/runtime/experience_extractor.py
.agentic-pi/runtime/learning_record_writer.py
.agentic-pi/runtime/strategy_memory.py
.agentic-pi/runtime/experience_retriever.py

.agentic-pi/schemas/experience_extract.schema.json
.agentic-pi/schemas/learning_record.schema.json
.agentic-pi/schemas/retrieved_experience.schema.json

.agentic-pi/memory/learning_records/.gitkeep
tests/test_experience_memory.py
```

## Flow

```text
completed run
-> experience_extract.json
-> append-only learning record
-> retrieved_experience.json
-> strategy_scorer.py advisory score adjustment
-> strategy selector
-> worker
-> certifier
```

## What Memory Records

```text
source_run_id
task_type
strategy_id
outcome
outcome_status
principle
do_not_use_when
evidence_files
```

Outcome classes:

```text
CERTIFIED_DONE / DONE_PASS -> success
PROVISIONAL_DONE -> provisional
NOT_DONE / DONE_FAIL / NEED_USER -> failure
```

## Guardrails

```text
memory can suggest
memory cannot write final_status.md
memory cannot write certification.json
memory cannot write policy_decision.json
memory cannot write verifier_artifacts/
memory cannot certify DONE
memory cannot bypass the applicability gate
```

Retrieved experience can add or subtract deterministic score deltas in
`strategy_scorer.py`, but only for strategies that already passed
`strategy_applicability_gate.py`.

The allowed score deltas are deliberately bounded:

```text
success -> +1
provisional -> -1
failure -> -2
unknown -> 0
```

`strategy_decision.json` records whether advisory memory influenced scoring, but
the decision status remains limited to strategy-selection states such as
`SELECTED` or `NEED_USER_STRATEGY`.

## Proof Commands

```cmd
python tests\test_experience_memory.py -v
python -m unittest discover tests -v
```

## Boundary

v1.7 proves:

```text
CERTIFIED_DONE run creates a success learning record
NOT_DONE run creates a failure learning record
PROVISIONAL_DONE records weak-verifier lesson
retrieved experience can adjust strategy score
blocked strategies remain blocked
unbounded memory score deltas are rejected
memory tools do not write status artifacts
```

v1.7 does not prove:

```text
memory quality across broad domains
semantic optimality of learned principles
long-term memory governance
domain packs
strategy search
full autonomous Pi goal-runner.chain.md runtime
```

Safe claim:

```text
The harness now has advisory experience memory for strategy scoring. Memory can
suggest; policy decides; certifier writes final status.
```
