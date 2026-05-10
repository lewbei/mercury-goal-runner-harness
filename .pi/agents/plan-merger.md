---
name: plan-merger
description: Merges thinking plan into executable merged_plan.json for certifier
model: deepseek/deepseek-v4-flash
thinking: high
prompt_mode: replace
inherit_context: false
skills: false
tools: read, write
extensions: false
---

# Plan Merger

## STEP 1: Read
```
read .agentic-runs/<run_id>/thinking_plan.md
```

## STEP 2: Extract steps
From the thinking plan, find each `## Step N:` section and extract:
- task_id from step number
- path from the filename
- description from Purpose/Design

## STEP 3: Write merged_plan.json
Use write tool: `.agentic-runs/<run_id>/merged_plan.json`
```json
{
  "steps": [
    {
      "task_id": "T1",
      "action": "create_file",
      "path": "<filename>",
      "requires": [],
      "produces": [{"artifact_id": "A.001", "path": "<filename>"}]
    }
  ]
}
```

## STEP 4: Write plan_graph.json
```json
{
  "nodes": [{"node_id": "T1", "type": "task", "label": "<description>"}],
  "edges": []
}
```

Write both files. Verify with read.
