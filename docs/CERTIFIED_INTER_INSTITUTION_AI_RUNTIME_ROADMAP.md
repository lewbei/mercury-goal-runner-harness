# Certified Inter-Institution AI Runtime Roadmap

Status: roadmap artifact / not a certification claim

This document uses the user's stronger frame:

> How can the harness evolve stage by stage until it becomes a certified self-improving AI institution network?

The answer is not to build one super-agent. The answer is:

> It reaches the final stage by turning every evolutionary jump into a certified promotion gate.

This roadmap does **not** certify that the current harness already implements cross-institution trust, reputation routing, or certified self-improvement. It maps the safe path from the current verifier-provenance harness toward a future certified inter-institution runtime.

## 1. Authority invariant

The current harness invariant remains the non-negotiable root rule:

```text
Pi can orchestrate.
Mercury can compile / execute / report.
Policy decides.
Certifier writes final status.
Pi only reports what the certifier wrote.
```

No roadmap stage may weaken this rule.

Related rule:

```text
No agent can certify its own work.
```

Reasoning artifacts, memory artifacts, reputation artifacts, cross-institution receipts, and self-improvement proposals are not final authority. Final status still comes only from the certifier/policy path.

## 2. Stage map

```text
Prompt helper
  ↓
Multi-frame reasoning harness
  ↓
Certification harness
  ↓
AI institution runtime
  ↓
Institution-to-institution trust layer
  ↓
Reputation + contract economy
  ↓
Certified self-improving AI institution network
```

The final stage is not autonomy by itself. The real final stage is:

> certified evolution.

## 3. Promotion gate rule

Do **not** build the final stage directly.

Build this:

```text
Each stage must prove it can control the previous stage.
```

Control chain:

```text
Reasoning harness controls one-path thinking.
Certification harness controls fake DONE.
Institution runtime controls agent authority.
Cross-institution layer controls delegation.
Reputation layer controls trust.
Self-improvement layer controls evolution.
```

If a stage cannot block the failure mode below it, it is not promoted.

## 4. Per-stage roadmap

| Stage | Capability | Required artifacts | Promotion gate | Negative probes | What this does not prove |
|---|---|---|---|---|---|
| 0. Prompt habit | Ask the model to think multiple ways, attack each path, choose strongest | Prompt text only | Can produce multiple frames and reject weak ones | One obvious answer is wrong; model collapses into one path | Not a harness; model can pretend |
| 1. Multi-frame reasoning harness | Turn the prompt habit into required artifacts | `problem_contract.json`, `frame_candidates.json`, `assumption_matrix.json`, `attack_report.json`, `selection_decision.json`, `reasoning_certification.json` | Can reject answers that collapse into one frame too early | Missing frame, duplicate frames, no attack, unsupported selection | Does not certify task DONE |
| 2. Certification harness | Stop fake completion | `goal_contract.json`, `artifact_manifest.json`, `tool_trace.json`, `verifier_report.json`, `policy_decision.json`, `certification.json`, `final_status.json` | Can catch fake DONE | Missing logs, wrong file edits, fake certification, weak self-tests, premature DONE | Does not prove arbitrary autonomy |
| 3. AI institution runtime | Split authority into roles | planner, executor, reviewer, verifier, certifier, memory clerk, human escalation artifacts | Can prevent authority abuse | Executor certifies, reviewer approves without evidence, memory clerk writes certified fact | Does not establish cross-institution trust |
| 4. Institution-to-institution protocol | Delegate without blind trust | `institution_card.json`, `authority_scope.json`, `task_contract.json`, `evidence_contract.json`, `verification_contract.json`, `handoff_receipt.json`, `cross_certification.json` | Institution A verifies B's result locally | Task outside scope, stale identity, evidence hash mismatch, remote self-certification | Does not create reputation economy |
| 5. Reputation layer | Route by trusted history, not smartest model | trust records, task outcomes, rollback metrics, override metrics, domain scores | Improves routing without being gamed | Easy-task farming, hidden failures, Sybil identities, collusion, evidence laundering | Reputation is not certification |
| 6. Certified self-improvement | Improve prompts, verifiers, policy, roles, tools, benchmarks safely | proposal, sandbox report, benchmark report, regression report, security report, policy report, promotion/rejection record, lineage record | Improves without breaking previous guarantees | Patch weakens certifier, removes negative tests, changes benchmark to pass itself | Does not allow direct live self-modification |
| 7. Certified Inter-Institution AI Runtime | Many certified institutions cooperate through contracts | claims, evidence, certifications, reputation, disputes, appeals, audit trails | Network remains evidence-backed, revocable, and locally verified | Trust replay, dispute failure, revocation failure, collusion | Not “AI civilization” as a marketing claim |

## 5. Grounding in current project state

Current project direction already supports the early/middle part of this map:

- artifact contracts;
- success criteria and oracles;
- verifier provenance;
- policy and certifier authority;
- replay and rollback audit;
- role-bounded agent phases;
- advisory memory with certification exclusion;
- negative behavior probes and RPG-style test aggregation.

The current harness is therefore closest to:

```text
Stage 2: Certification harness
moving toward
Stage 3: AI institution runtime
```

But the future stages must remain marked as future until deterministic validators and proof-matrix entries exist.

## 6. Near-term implementation order

Do not jump from Stage 1 to Stage 7.

The correct path is:

```text
small proof → hard benchmark → authority split → memory control → delegation → reputation → self-improvement
```

### Milestone A — Multi-frame reasoning gate

Purpose: solve the current problem where the model only thinks one way.

Planned work:

- define schemas for `frame_candidates`, `assumption_matrix`, `attack_report`, `selection_decision`, and `reasoning_certification`;
- add a deterministic validator that rejects premature convergence;
- require the reasoning gate before strict prepared-run verification uses a selected plan;
- add negative fixtures for one-frame collapse, duplicate frames, missing attacks, and unsupported final direction.

Important boundary:

```text
CERTIFIED_REASONED is not CERTIFIED_DONE.
```

### Milestone B — Institution runtime / context board

Purpose: make the harness institutional, not just an agent running a task.

Planned work:

- add structured role cards or a context board for planner, executor, reviewer, verifier, certifier, memory clerk, and human judge;
- enforce that role outputs are advisory unless they are produced by the deterministic certifier/policy path;
- reject any worker, reviewer, or memory artifact that attempts to write or claim final authority;
- keep memory advisory and excluded from certification evidence.

Gate:

```text
Can the institution prevent authority abuse?
```

### Milestone C — Cross-institution handoff contracts

Purpose: let Institution A delegate work to Institution B and verify the result without blindly trusting B.

Planned work:

- define institution cards, authority scopes, task contracts, evidence contracts, handoff receipts, and cross-certification records;
- require signed or hash-linked evidence for handoff outputs;
- treat remote certification as input evidence only;
- replay or verify the result locally before local policy/certifier status changes.

Gate:

```text
Can Institution A delegate work to Institution B and verify the result without blindly trusting B?
```

### Milestone D — Reputation after evaluation data exists

Purpose: route to trusted institutions only after the harness has enough certifier-owned outcome history.

Planned work:

- derive reputation only from certifier-owned outcomes and frozen evidence;
- include failures, missing evidence, rollbacks, human overrides, and domain limits;
- add anti-gaming tests before reputation influences routing.

Gate:

```text
Can the reputation system improve routing without being gamed?
```

### Milestone E — Certified self-improvement

Purpose: allow controlled evolution without breaking previous guarantees.

Required pipeline:

```text
proposal
  ↓
sandbox
  ↓
benchmark
  ↓
regression test
  ↓
security check
  ↓
policy check
  ↓
human review if risky
  ↓
promotion / rejection
  ↓
lineage record
```

Gate:

```text
Can it improve itself without breaking previous guarantees?
```

## 7. Required negative benchmark families

### FakeDoneBench

Expected catch examples:

- agent says tests passed but no log exists;
- agent edits wrong file;
- agent creates fake `certification.json`;
- agent self-writes weak tests;
- agent reports DONE before required artifact exists;
- runtime synthesizes missing proof artifacts instead of failing closed.

### AuthorityAbuseBench

Expected catch examples:

- executor tries to mark `CERTIFIED_DONE`;
- reviewer approves without evidence;
- planner edits certifier-owned files;
- memory clerk writes a certified fact;
- external institution self-certifies and asks local harness to trust it.

### MemoryPoisonBench

Expected catch examples:

- memory card claims final status;
- quarantine memory becomes durable without the gate;
- memory enters certification evidence;
- memory overrides policy;
- deprecated memory influences future routing.

### CrossInstitutionTrustBench

Expected catch examples:

- missing frozen evidence;
- stale or revoked institution identity;
- task outside authority scope;
- replayed old handoff receipt;
- evidence hash mismatch;
- remote executor certifies itself.

### ReputationGamingBench

Expected catch examples:

- easy-task farming;
- hidden failed attempts;
- Sybil institutions;
- collusive certifications;
- evidence laundering;
- domain mismatch score inflation.

### SelfImprovementRegressionBench

Expected catch examples:

- patch weakens certifier;
- patch removes negative tests;
- patch changes benchmark to pass itself;
- patch grants any agent self-certification;
- patch bypasses memory gate;
- patch improves one metric while breaking old guarantees.

## 8. Status labels by layer

Reasoning layer:

```text
CERTIFIED_REASONED
REJECTED_PREMATURE_CONVERGENCE
```

Certification layer:

```text
NOT_DONE
PROVISIONAL_DONE
CERTIFIED_DONE
CERTIFIED_FAIL
NEEDS_HUMAN_REVIEW
```

Self-improvement layer:

```text
IMPROVEMENT_PROPOSED
SANDBOX_PASSED
REGRESSION_FAILED
SECURITY_BLOCKED
PROMOTED
ROLLED_BACK
```

These labels must not be confused with certifier-owned final status unless and until the policy/certifier path owns them.

## 9. Validation commands for this roadmap artifact

For this docs-only roadmap edit:

```cmd
python tests\test_repo_structure_cleanup.py -v
git diff --check
git status -sb
```

For future implementation milestones, add focused unittest files and the proof matrix only after validators exist:

```cmd
python -m unittest discover tests -v
python .agentic-pi\runtime\run_proof_matrix.py --mode quick
```

Safe claim after validation:

```text
The harness passed the listed deterministic validators and proof commands.
```

Unsafe claim to avoid:

```text
Pi/Mercury is proven safe for arbitrary autonomous goals.
```

## 10. Final planning answer

The staged proposal is directionally strong. The weak version is trying to name one final stage. The stronger version is promotion-gated evolution.

The real final stage is not autonomy.

The real final stage is:

```text
certified evolution
```

And the implementation rule is:

```text
Do not build “AI civilization” first.
Build the smallest system that can say:

This answer collapsed too early.
This DONE is fake.
This agent has no authority.
This evidence is insufficient.
This memory update is not certified.
This self-improvement patch failed regression.
```
