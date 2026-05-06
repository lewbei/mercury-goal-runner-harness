# Plan Selector

**Purpose**: Choose the best plan(s) from one or more planner outputs based on criteria such as step count, risk, and resource usage.

**Input**: Multiple `plan.json` files from different planners.

**Output**: `selected_plan.json` containing the chosen plan (or a list of top plans).

**Strategy**:
- Score each plan on length, safety checks, and skeptic findings.
- Prefer shorter plans if they meet a minimum safety threshold.
- Return the highest‑scoring plan.
