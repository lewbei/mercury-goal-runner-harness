# Thinking Plan: Perfect Square Checker

## Architecture
Only a single Python module is needed: `is_perfect_square.py`. This file contains the core function and a simple CLI for manual verification. No additional modules, tests, or configuration files are required for the goal contract.

## Design decisions
| Decision | Options | Chosen | Why |
|----------|---------|--------|-----|
| Perfect square detection method | 1. `math.sqrt` and check `int(sqrt) ** 2 == n` (floating point) <br> 2. `math.isqrt` and compare `isqrt ** 2 == n` (integer) | `math.isqrt` | Avoids floating‑point inaccuracies and works for arbitrarily large integers. `math.isqrt` is O(log n) and available in Python 3.8+. |
| Error handling for non‑int input | 1. Implicit Python TypeError <br> 2. Explicit type check with `#@ Requires` annotation | Explicit type check via `#@ Requires` | Guarantees a clear error message and satisfies the contract that the function only accepts integers. |
| Return value on negative numbers | 1. Raise ValueError <br> 2. Return `False` | Return `False` | A negative number cannot be a perfect square in the integer domain, and returning `False` keeps the function pure and easy to use. |

---

## Step 1: is_perfect_square.py

### Why
This is the sole artifact required to satisfy the goal contract. It implements the perfect‑square check and provides a simple command‑line demonstration that produces at least two lines of output when executed.

### Design
The module defines a single public function `is_perfect_square`. It uses `math.isqrt` for integer square‑root calculation, checks the square, and returns a boolean. Input validation is performed via a `#@ Requires` annotation, and the post‑condition is documented with `#@ Ensures`. The `__main__` block runs a small demo on a set of test numbers, printing one line per number (more than two lines).

### Template
```python
"""is_perfect_square.py

Utility module that provides a function to check whether a given integer is a perfect square.
"""

import math
from typing import Any

#@ Requires(lambda n: isinstance(n, int), "Input must be an integer")
#@ Ensures(lambda result, n: isinstance(result, bool), "Result must be a boolean")
def is_perfect_square(n: int) -> bool:
    """Return ``True`` if *n* is a perfect square, otherwise ``False``.

    Args:
        n: Integer to test. Negative numbers are not perfect squares.

    Returns:
        ``True`` if *n* is a perfect square, ``False`` otherwise.
    """
    if n < 0:
        return False
    # Use integer square root to avoid floating‑point errors.
    root = math.isqrt(n)
    return root * root == n


if __name__ == "__main__":
    # Simple manual test suite – prints one line per number (>=2 lines).
    test_numbers = [0, 1, 2, 4, 10, 16, -4]
    for num in test_numbers:
        print(f"{num}: {is_perfect_square(num)}")
```

### Validation
Run the module directly:

```bash
python is_perfect_square.py
```
You should see at least two lines of output, e.g.:
```
0: True
1: True
2: False
4: True
10: False
16: True
-4: False
```
The output confirms that the function behaves correctly for typical, edge‑case, and negative inputs.
