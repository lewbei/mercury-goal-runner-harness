# Planner Minimal

**Purpose**: Generate the shortest viable plan for a given Goal Contract.

**Input**: Goal Contract JSON.

**Output**: `plan.json` containing a list of steps with minimal tool usage.

**Strategy**:
- Identify required output files.
- Choose the simplest sequence of actions.
- Avoid optional checks and safety steps.

**When to use**: Simple goals where speed is preferred over robustness.
