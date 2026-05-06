# Planner Robust

**Purpose**: Generate a safe, thorough plan that includes validation and fallback steps.

**Input**: Goal Contract JSON.

**Output**: `plan.json` with detailed steps, checks, and error handling.

**Strategy**:
- Validate preconditions before each step.
- Include verification steps after critical actions.
- Plan for rollback on failure.

**When to use**: Medium or complex goals where correctness and safety are important.
