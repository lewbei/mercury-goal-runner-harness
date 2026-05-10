# Thinking Plan: Factorial Function

## Architecture
The solution consists of a single Python module `factorial.py` that provides a function `factorial`. This module is sufficient to satisfy the goal contract, which only requires the existence of `factorial.py`. No additional files (tests, documentation) are mandated, keeping the implementation minimal and focused.

## Design decisions
| Decision | Options | Chosen | Why |
|----------|---------|--------|-----|
| Implementation method | Recursive, Iterative | Iterative | Iterative avoids recursion depth limits and is easier to understand for a simple function. |
| Error handling for negative input | Return `None`, Raise `ValueError`, Return `-1` | Raise `ValueError` | Raising an exception makes the failure explicit and aligns with Pythonic error handling. |

---

## Step 1: factorial.py

### Why
Creating the core implementation first establishes the primary artifact required by the goal contract. All subsequent validation depends on this file existing and containing correct logic.

### Design
- **Signature**: `def factorial(n: int) -> int`
- **Docstring**: Describes purpose, arguments, return value, and raised exceptions.
- **Error handling**: Raises `ValueError` for negative inputs.
- **Algorithm**: Iterative multiplication from 2 to `n` to compute the factorial.
- **Edge cases**: Handles `n = 0` and `n = 1` correctly (returns 1).

### Template
```python

def factorial(n: int) -> int:
    """Return the factorial of a non‑negative integer n.

    Args:
        n: A non‑negative integer.

    Returns:
        The factorial of n.

    Raises:
        ValueError: If n is negative.
    """
    if n < 0:
        raise ValueError("Factorial is undefined for negative numbers")
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result
```

### Validation
Run a quick sanity check from the command line:

```bash
python -c "from factorial import factorial; assert factorial(0) == 1; assert factorial(5) == 120"
```

If the command exits without error, the implementation meets the `done_criteria` of the contract.
