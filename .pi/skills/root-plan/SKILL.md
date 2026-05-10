# Root Plan Skill

**Phase:** PLANNING
**Role:** Planner
**Artifact:** `thinking_plan.md`

## Purpose

Produce a design document that shows your reasoning AND contains the code templates the implementer will use. This is the source of truth for the implementation phase.

## Output Format

A markdown document. Every file gets its own numbered step with reasoning first, template second.

```markdown
# Thinking Plan: <goal name>

## Architecture
Why this structure? What files? What lives where? How do they connect?

## Design decisions
For each non-obvious choice: what options did you consider? Which did you pick? Why?

---

## Step 1: <file1.py>

### Why
Why is this step first? What does it establish? What depends on it?

### Design
How should this file work? Edge cases? Error handling? Tradeoffs considered?

### Template
```python
# <file1.py>
<complete code — no TODOs, no placeholders>
```

### Validation
How to verify this step works before moving on. Give exact commands.

---

## Step 2: <file2.py>

### Why
Why second? What does it depend on from Step 1?

### Design
...

### Template
```python
...
```

### Validation
...

---

## Step N: ...
```

## Rules

1. Show your design REASONING — WHY every decision, not just WHAT
2. Every function/class needs a full signature, docstring, and body description in the template
3. Error handling must be explicit — which exceptions, under what conditions
4. Compare alternatives for every non-obvious choice (e.g., "Option A return None vs Option B raise exception — chose B because...")
5. The implementer must be able to code every file from the templates alone — no guessing, no "figure it out"
6. Keep it focused — only files needed to satisfy the goal contract

## Validators Applied

None. The thinking plan is a human-readable design document. The certifier validates step_logs and artifacts, not the plan format.

## Authority Boundaries

- Do NOT execute any code
- Do NOT write authority files
- Do NOT certify
- Do NOT produce machine-readable plan_graph.json — that is derived later if needed
