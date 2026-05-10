# Thinking Plan: Implement numerical_letter_grade

## Architecture
The solution consists of a single Python module `numerical_letter_grade.py`. This module provides the `numerical_letter_grade` function, which converts a list of GPA values to their corresponding letter grades based on the provided mapping. No additional files are required because the contract only specifies a single output artifact.

## Design decisions
| Decision | Options | Chosen | Why |
|----------|---------|--------|-----|
| Mapping implementation | (1) Sequential if‑elif chain, (2) List of thresholds with loop, (3) Binary search on sorted thresholds | 1 – Sequential if‑elif chain | The mapping is small (13 cases) and includes exact matches for 4.0 and 0.0. An if‑elif chain is the most readable and has negligible performance impact for the expected input size. |
| Error handling | (1) Silent ignore invalid values, (2) Return `None` for invalid values, (3) Raise `ValueError` | 3 – Raise `ValueError` | The contract expects a correct mapping for valid GPAs. Raising an exception makes misuse explicit and simplifies debugging. |
| Type of input | (1) Any iterable, (2) List only | 1 – Any iterable | Allows flexibility (e.g., tuple, generator) while still returning a list as required. |

---

## Step 1: numerical_letter_grade.py

### Why
This is the core artifact that fulfills the contract's `final_outputs`. Implementing it first establishes the primary functionality on which any optional tests or wrappers would depend.

### Design
- **Function signature**: `def numerical_letter_grade(grades):`
- **Docstring**: Include the description from the contract, explaining the mapping and providing an example.
- **Implementation**: Iterate over the input `grades`, validate each GPA, and map it to a letter grade using an if‑elif chain that respects the exact thresholds.
- **Error handling**: Raise `ValueError` for any GPA outside the inclusive range `[0.0, 4.0]`.
- **Return value**: A list of letter grades in the same order as the input.

### Template
```python
# numerical_letter_grade.py

def numerical_letter_grade(grades):
    """
    Convert a list of GPA values to letter grades.

    The mapping follows the table:
        GPA   | Letter grade
        4.0   | A+
        >3.7  | A
        >3.3  | A-
        >3.0  | B+
        >2.7  | B
        >2.3  | B-
        >2.0  | C+
        >1.7  | C
        >1.3  | C-
        >1.0  | D+
        >0.7  | D
        >0.0  | D-
        0.0   | E

    Example:
        >>> numerical_letter_grade([4.0, 3, 1.7, 2, 3.5])
        ['A+', 'B', 'C-', 'C', 'A-']

    Parameters
    ----------
    grades : iterable of float
        GPA values to convert. Each value must be between 0.0 and 4.0 inclusive.

    Returns
    -------
    list of str
        Corresponding letter grades.

    Raises
    ------
    ValueError
        If any GPA is outside the allowed range.
    """
    result = []
    for g in grades:
        # Validate GPA range
        if not isinstance(g, (int, float)):
            raise TypeError(f"GPA value {g!r} is not a number")
        if g < 0.0 or g > 4.0:
            raise ValueError(f"GPA {g} is out of range [0.0, 4.0]")

        # Exact matches first
        if g == 4.0:
            result.append("A+")
        elif g > 3.7:
            result.append("A")
        elif g > 3.3:
            result.append("A-")
        elif g > 3.0:
            result.append("B+")
        elif g > 2.7:
            result.append("B")
        elif g > 2.3:
            result.append("B-")
        elif g > 2.0:
            result.append("C+")
        elif g > 1.7:
            result.append("C")
        elif g > 1.3:
            result.append("C-")
        elif g > 1.0:
            result.append("D+")
        elif g > 0.7:
            result.append("D")
        elif g > 0.0:
            result.append("D-")
        else:  # g == 0.0
            result.append("E")
    return result

# Optional: simple sanity check when run as a script
if __name__ == "__main__":
    sample = [4.0, 3, 1.7, 2, 3.5]
    print("Input:", sample)
    print("Output:", numerical_letter_grade(sample))
```

### Validation
To verify the implementation before proceeding:

```bash
# 1. Run the module directly to see the sanity check output
python numerical_letter_grade.py

# 2. Execute an interactive test
python - <<'PY'
from numerical_letter_grade import numerical_letter_grade
assert numerical_letter_grade([4.0, 3, 1.7, 2, 3.5]) == ['A+', 'B', 'C-', 'C', 'A-']
print("All assertions passed.")
PY
```

If both commands complete without errors and the printed output matches the expected example, the step is considered valid.

---
