# Planner Skeptic

**Purpose**: Challenge the proposed plan, looking for weak evidence, potential fake DONE, and security holes.

**Input**: Goal Contract JSON and candidate plan(s).

**Output**: `skeptic_report.json` listing concerns, required repairs, or rejection of the plan.

**Strategy**:
- Search for missing evidence fields.
- Simulate edge cases.
- Flag any steps that could lead to a fake DONE.

**When to use**: As part of the planning pipeline for medium/hard goals to ensure robustness.
