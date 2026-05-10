# Thinking Plan: below_zero function

## Architecture
The solution consists of a single Python module `below_zero.py`. This module provides the core `below_zero` function required by the goal contract. No additional files (e.g., tests, configuration) are needed to satisfy the `done_criteria`, which only requires the existence of `below_zero.py` with a correct implementation.

## Design decisions
- **Implementation approach**: We considered two main approaches:
  1. **Iterative loop** – straightforward, O(n) time, O(1) space, easy to add explicit error handling.
  2. **`itertools.accumulate` + `any`** – more functional, but introduces an extra import and makes per‑element validation less clear.
  We chose the **iterative loop** because it is the most readable for a simple algorithm, and it allows us to raise precise `TypeError` messages for malformed input.
- **Error handling**: The contract does not explicitly require input validation, but robust code should fail fast on incorrect types. We therefore validate that `operations` is a list and that each element is an `int`. If validation fails, a `TypeError` is raised with a helpful message.
- **Edge cases**: An empty list should return `False` (balance never goes below zero). Large integer values are handled naturally by Python's arbitrary‑precision ints.
- **Documentation**: A comprehensive docstring explains the purpose, arguments, return value, and possible exceptions.

---

## Step 1: below_zero.py

### Why
This is the first and only step because the goal contract's `final_outputs` only requires a single file `below_zero.py`. Implementing this file establishes the core functionality and satisfies the `done_criteria`.

### Design
- The function receives a `List[int]`.
- Validate input types early.
- Iterate through the operations, updating a running `balance`.
- Return `True` immediately when `balance < 0`.
- If the loop finishes without a negative balance, return `False`.
- Provide a clear docstring and type hints.
- No external dependencies are required.

### Template
```python
# below_zero.py
from typing import List


def below_zero(operations: List[int]) -> bool:
    """Return ``True`` if the cumulative balance ever falls below zero.

    The account starts at a balance of zero. Each element of ``operations`` is an
    integer representing a deposit (positive) or withdrawal (negative). The function
    processes the list sequentially, updating the balance after each operation. If at
    any point the balance becomes negative, ``True`` is returned; otherwise ``False``.

    Args:
        operations: A list of integer amounts. Positive values deposit money, negative
            values withdraw money.

    Returns:
        ``True`` if the balance is negative at any point, ``False`` otherwise.

    Raises:
        TypeError: If ``operations`` is not a list or contains non‑integer items.
    """
    # Validate that the input is a list
    if not isinstance(operations, list):
        raise TypeError("operations must be a list of integers")

    balance = 0
    for idx, op in enumerate(operations):
        # Validate each element is an integer
        if not isinstance(op, int):
            raise TypeError(f"operation at index {idx} is not an integer: {op!r}")
        balance += op
        if balance < 0:
            return True
    return False
```

### Validation
Run the following command in the repository root to execute a quick sanity check:

```bash
python - <<'PY'
from below_zero import below_zero
assert below_zero([1, 2, 3]) is False
assert below_zero([1, 2, -4, 5]) is True
assert below_zero([]) is False
assert below_zero([0, 0, 0]) is False
print('All validation checks passed.')
PY
```

If the script prints *All validation checks passed.*, the implementation meets the contract.
