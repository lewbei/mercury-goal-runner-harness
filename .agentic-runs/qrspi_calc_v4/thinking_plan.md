# Thinking Plan: Simple Python Calculator

## Architecture

The solution consists of two Python files placed at the root of the run directory:
1. **calculator.py** – a pure‑Python module exposing four arithmetic functions: `add`, `subtract`, `multiply`, and `divide`. The module is deliberately lightweight: it contains only the function implementations, type hints, and a small `__all__` list to define the public API. No external dependencies are required, keeping the module easy to import in any environment.
2. **test_calculator.py** – a test suite written using the built‑in `unittest` framework. Tests are isolated per operation and include edge‑case verification (e.g., division by zero). The test file imports the public symbols from `calculator.py` and can be executed directly via `python -m unittest test_calculator.py`.

This two‑file structure mirrors the classic “module + unit tests” pattern and satisfies the goal contract while remaining simple enough for a junior developer to implement.

## Design decisions

| Decision | Options considered | Chosen approach | Rationale |
|----------|-------------------|----------------|-----------|
| **Error handling for division** | Return `float('inf')`, return `None`, raise a custom exception, raise built‑in `ZeroDivisionError` | Raise the built‑in `ZeroDivisionError` with a clear message | Using the standard exception aligns with Python’s arithmetic semantics, requires no custom exception class, and is automatically caught by `unittest`’s `assertRaises`. |
| **Type hints** | No type hints, full type hints (`int | float`) | Full type hints for all parameters and return values | Improves readability, enables static analysis, and matches modern Python best practices. |
| **Testing framework** | `pytest`, `unittest`, simple script with assertions | `unittest` (standard library) | No third‑party dependencies; the repository may be run on any Python installation without extra packages. |
| **Public API definition** | Implicit via naming, explicit `__all__` | Explicit `__all__` list | Makes the intended public symbols clear and prevents accidental export of helper objects. |
| **Error messages** | Generic, detailed | Detailed message for division by zero (`"Cannot divide by zero"`) | Provides useful feedback for developers and makes test assertions straightforward. |

## Files

### calculator.py

**Purpose:** Provide four basic arithmetic operations with proper type hints and error handling.
**Exports:** `add`, `subtract`, `multiply`, `divide` (exposed via `__all__`).
**Dependencies:** None (standard library only).

#### Design

* Each function accepts two numbers (`int` or `float`) and returns a `float` (or `int` when both inputs are integers and the operation yields an integer). The implementation uses Python’s built‑in arithmetic operators.
* `divide` checks the denominator and raises `ZeroDivisionError` with a custom message if it is zero.
* Input validation is minimal: the functions rely on Python’s dynamic typing; passing non‑numeric types will naturally raise a `TypeError` which is acceptable for this simple module.
* The module defines `__all__` to make the public API explicit.

#### Template

```python
# calculator.py
"""Simple arithmetic calculator module.

Provides four functions: :func:`add`, :func:`subtract`, :func:`multiply`, and :func:`divide`.
All functions accept ``int`` or ``float`` arguments and return a numeric result.
"""

from __future__ import annotations

__all__: list[str] = ["add", "subtract", "multiply", "divide"]


def add(a: int | float, b: int | float) -> int | float:
    """Return the sum of *a* and *b*.

    Args:
        a: First addend.
        b: Second addend.

    Returns:
        The arithmetic sum of *a* and *b*.
    """
    return a + b


def subtract(a: int | float, b: int | float) -> int | float:
    """Return the difference of *a* minus *b*.

    Args:
        a: Minuend.
        b: Subtrahend.

    Returns:
        The result of *a* - *b*.
    """
    return a - b


def multiply(a: int | float, b: int | float) -> int | float:
    """Return the product of *a* and *b*.

    Args:
        a: First factor.
        b: Second factor.

    Returns:
        The arithmetic product of *a* and *b*.
    """
    return a * b


def divide(a: int | float, b: int | float) -> float:
    """Return the quotient of *a* divided by *b*.

    Args:
        a: Numerator.
        b: Denominator.

    Raises:
        ZeroDivisionError: If *b* is zero.

    Returns:
        The quotient as a ``float``.
    """
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b
```

### test_calculator.py

**Purpose:** Verify that each arithmetic function works correctly, including edge cases such as division by zero.
**Exports:** None (test module executed by `unittest`).
**Dependencies:** `unittest`, and the public symbols from `calculator`.

#### Design

* Use `unittest.TestCase` subclasses to group related tests.
* Each operation has a dedicated test method covering typical integer and floating‑point inputs.
* The division‑by‑zero case uses `assertRaises` to confirm the correct exception and message.
* The test suite can be run via `python -m unittest test_calculator.py` or `python test_calculator.py` (the latter includes a `if __name__ == "__main__"` guard).

#### Template

```python
# test_calculator.py
"""Unit tests for the ``calculator`` module.
"""

import unittest
from calculator import add, subtract, multiply, divide


class TestCalculator(unittest.TestCase):
    """Test suite for basic arithmetic functions."""

    # --- Add ---
    def test_add_integers(self):
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-1, 1), 0)

    def test_add_floats(self):
        self.assertAlmostEqual(add(2.5, 3.1), 5.6)

    # --- Subtract ---
    def test_subtract_integers(self):
        self.assertEqual(subtract(10, 4), 6)
        self.assertEqual(subtract(-5, -5), 0)

    def test_subtract_floats(self):
        self.assertAlmostEqual(subtract(5.5, 2.2), 3.3)

    # --- Multiply ---
    def test_multiply_integers(self):
        self.assertEqual(multiply(3, 7), 21)
        self.assertEqual(multiply(-2, 4), -8)

    def test_multiply_floats(self):
        self.assertAlmostEqual(multiply(1.5, 2.0), 3.0)

    # --- Divide ---
    def test_divide_integers(self):
        self.assertAlmostEqual(divide(10, 2), 5.0)
        self.assertAlmostEqual(divide(-9, 3), -3.0)

    def test_divide_floats(self):
        self.assertAlmostEqual(divide(7.5, 2.5), 3.0)

    def test_divide_by_zero(self):
        with self.assertRaises(ZeroDivisionError) as cm:
            divide(5, 0)
        self.assertEqual(str(cm.exception), "Cannot divide by zero")

if __name__ == "__main__":
    unittest.main()
```

## Dependencies between files

1. **calculator.py** must exist before **test_calculator.py** can be imported. The test file imports the four functions directly from the calculator module, so the module must be importable (i.e., located in the same directory or on the Python path). No circular dependencies exist.

The implementer should first create `calculator.py` using the template above, then create `test_calculator.py`. After both files are in place, running the tests will confirm that the implementation meets the goal contract.
