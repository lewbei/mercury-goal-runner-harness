# Thinking Plan: Prime Checker

## Architecture
The solution consists of two Python modules:
- **is_prime.py** – Implements the core `is_prime` function.
- **test_is_prime.py** – Contains unit tests using `pytest` to validate the implementation.

The architecture follows a simple separation of concerns: the implementation module is independent and can be imported by any client, while the test module exercises the public API and checks edge cases. This design keeps the codebase minimal (aligned with the "EASY" complexity level) and straightforward to extend.

## Design decisions
| Decision | Options | Chosen | Why |
|---|---|---|---|
| **Algorithm** | Trial division (up to √n) vs Miller‑Rabin probabilistic test | Trial division | For small numbers and an easy‑level goal, trial division is simple, deterministic, and requires no external dependencies. |
| **Input validation** | Duck‑typing (let Python raise errors) vs explicit `isinstance` check | Explicit `isinstance` check | Guarantees a clear `TypeError` for non‑int inputs, making the contract's success criteria deterministic. |
| **Output type** | Return `bool` vs raise exception for non‑prime | Return `bool` | The contract expects a function that *checks* primality, not one that signals failure via exceptions. |
| **Optimization** | Simple loop vs 6k±1 step optimization | 6k±1 optimization | Reduces the number of iterations roughly by a factor of three while staying easy to understand. |

---

## Step 1: is_prime.py

### Why
This is the primary artifact required by the goal contract. Implementing the prime‑checking logic first establishes the core functionality that subsequent steps (e.g., testing) will depend on.

### Design
- **Signature**: `def is_prime(n: int) -> bool`
- **Docstring**: Describes purpose, parameters, return value, and raised exceptions.
- **Error handling**: Raises `TypeError` for non‑int inputs; returns `False` for integers < 2.
- **Algorithm**: Handles trivial cases (2, 3) directly, eliminates even numbers, then checks divisibility using the 6k ± 1 pattern up to `sqrt(n)`.
- **Edge cases**: `0`, `1`, negative numbers, non‑int types.

### Template
```python
def is_prime(n: int) -> bool:
    """
    Determine whether a given integer is a prime number.

    Parameters
    ----------
    n : int
        The integer to test. Must be a non‑negative integer.

    Returns
    -------
    bool
        True if ``n`` is prime, False otherwise.

    Raises
    ------
    TypeError
        If ``n`` is not an integer.
    """
    # Input type validation
    if not isinstance(n, int):
        raise TypeError(f"Expected int, got {type(n).__name__}")

    # Numbers less than 2 are not prime
    if n < 2:
        return False

    # Handle small primes directly
    if n in (2, 3):
        return True

    # Eliminate even numbers and multiples of 3 early
    if n % 2 == 0 or n % 3 == 0:
        return False

    # Check potential factors using 6k ± 1 optimization
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6

    return True
```

### Validation
Run a quick manual sanity check or execute the test suite (Step 2). Example manual check:
```python
>>> from is_prime import is_prime
>>> is_prime(29)
True
>>> is_prime(30)
False
```

---

## Step 2: test_is_prime.py

### Why
Testing verifies that the implementation satisfies the contract's success criteria (correctness across typical and edge cases). This step depends on the artifact produced in Step 1.

### Design
- Uses `pytest` for concise parameterized tests.
- Covers:
  - Base cases (`0`, `1`, `2`, `3`).
  - Small composites and primes.
  - Larger numbers to exercise the loop.
  - Invalid input types to confirm `TypeError` is raised.

### Template
```python
import pytest
from is_prime import is_prime

@pytest.mark.parametrize(
    "value,expected",
    [
        (0, False),
        (1, False),
        (2, True),
        (3, True),
        (4, False),
        (5, True),
        (16, False),
        (17, True),
        (19, True),
        (20, False),
        (23, True),
        (24, False),
        (29, True),
        (97, True),
        (100, False),
    ],
)
def test_is_prime(value, expected):
    assert is_prime(value) == expected

\ test_invalid_type():
    with pytest.raises(TypeError):
        is_prime(3.14)
    with pytest.raises(TypeError):
        is_prime("13")
```

### Validation
Execute the test suite:
```bash
pytest test_is_prime.py
```
All tests should pass, confirming the implementation meets the contract.
