# Thinking Plan: memory_read

## Architecture
Add a STEP 0 to the planner prompt to query durable memory before reading skills. This ensures the planner can incorporate relevant past learnings and avoid known failures.

## Design decisions
| Decision | Options | Chosen | Why |
|---|---|---|---|
| Include memory query step | Yes/No | Yes | Must incorporate past learnings to improve planning quality |
| Where to place step | Before reading skills / After reading skills | Before reading skills | Memory may influence which skills to prioritize |
| How to query memory | List files / Search for keywords / Load all | Search for keywords | Efficient and relevant |

---

## Step 0: Query Durable Memory
### Why
Before reading any skill definitions, the planner should consult the durable memory store to retrieve any past learnings that are relevant to the current goal. This can prevent repeating known failures and leverage previous solutions.

### Design
The planner will scan the directory `.agentic-pi/memory/durable/` for files that contain keywords from the goal contract description. It will load the content of matching files and make them available as context for subsequent steps.

### Template
No code is generated in this step; it is an instruction for the planner to perform a memory query.

---

## Step 1: Read inputs (MANDATORY)
Read ALL 5 skills:
```
read .agentic-pi/skills/question-contract/SKILL.md
read .agentic-pi/skills/research-pack/SKILL.md
read .agentic-pi/skills/design-options/SKILL.md
read .agentic-pi/skills/structure-outline/SKILL.md
read .agentic-pi/skills/root-plan/SKILL.md
```

Read the contract:
```
read .agentic-runs/<run_id>/goal_contract.json
```

---

## Step 2: Write the plan (MANDATORY)
Use write tool to save `.agentic-runs/<run_id>/thinking_plan.md`:

```markdown
# Thinking Plan: <name>

## Architecture
<why this structure?>

## Design decisions
| Decision | Options | Chosen | Why |

---

## Step 1: <file.py>
### Why
### Design
### Template
```python
<COMPLETE CODE - no TODOs>
```
if __name__ == "__main__":
    # Quick test - must produce 2+ lines of output
    print("Testing <function>")
    print(f"Result: {<function>(<test_input>)}")
```

---

## Step 3: Write plan_graph.json (MANDATORY)
Use write tool to save `.agentic-runs/<run_id>/plan_graph.json`:

```json
{
  "nodes": [
    {"node_id": "step1", "type": "task", "task_id": "step1"},
    {"node_id": "output_file.py", "type": "artifact", "path": "output_file.py", "artifact_id": "output_file.py"}
  ],
  "edges": [
    {"source": "step1", "target": "output_file.py", "type": "produces"}
  ]
}
```

CRITICAL rules for plan_graph:
- Produce 1 task node + 1 artifact node unless the goal contract names multiple files
- node_id for tasks MUST match the task_id (e.g., "step1") — NOT "n0", "n1"
- node_id for artifacts MUST be the actual filename (e.g., "validate_email.py")
- artifact nodes MUST have both "path" and "artifact_id" fields set to the filename
- edge type MUST be "produces" or "requires" (NO "flow", "output", "depends")
- task nodes: task_id is required. artifact nodes: task_id is NOT needed, but path and artifact_id ARE required

---

## Step 4: Write merged_plan.json (MANDATORY)
Use write tool to save `.agentic-runs/<run_id>/merged_plan.json`:

```json
{
  "steps": [
    {"task_id": "step1", "action": "create_file", "path": "output_file.py", "requires": [], "produces": ["output_file.py"]}
  ]
}
```

CRITICAL rules for merged_plan:
- Produce exactly 1 step unless the goal contract explicitly names multiple files
- task_id MUST match plan_graph node_id (e.g., "step1")
- action MUST be "create_file" (not "write" or "Implement")
- requires/produces are arrays of filenames (strings)
- Do NOT add test file steps — the verifier handles testing independently

---

## Step 5: READ-BACK VERIFICATION (MANDATORY)
After writing all three files, verify each one exists:
```
read .agentic-runs/<run_id>/thinking_plan.md
read .agentic-runs/<run_id>/plan_graph.json
read .agentic-runs/<run_id>/merged_plan.json
```
Each read MUST return the file content. If any read fails, write that file again, then read again.
Do NOT claim files are written unless you executed the read tool and saw the content.

---

## RULES
- Every function has signature, docstring, body
- Template is COMPLETE code, not placeholders
- Use write tool — NEVER output plan as text only
- Produce ONLY the implementation file. Do NOT add test files unless the goal contract explicitly requires tests.
- merged_plan.json must have EXACTLY the same number of steps as the worker will implement.
- If the goal says 'Write a function that does X', that is 1 step, 1 file.

## DO NOT
- Output plan as conversation text without calling write
- Produce JSON instead of markdown
- Skip reading skills or contract
- Claim files exist without executing the read tool
