# Plan Merger

**Purpose**: Merge multiple selected plans into a single coherent execution plan.

**Input**: `selected_plan.json` (may contain multiple plans).

**Output**: `merged_plan.json` with a unified ordered list of steps, deduplicated and reconciled.

**Strategy**:
- Concatenate steps while preserving dependencies.
- Remove duplicate actions.
- Resolve conflicts by preferring the most robust step.
