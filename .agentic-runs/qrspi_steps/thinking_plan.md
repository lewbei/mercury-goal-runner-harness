# Thinking Plan: Create calculator.py and test_calculator.py

## Architecture
The solution consists of a simple Python module `calculator.py` exposing four arithmetic functions, and a unit‑test suite `test_calculator.py` using the built‑in `unittest` framework. Keeping the implementation and its tests in separate files follows standard Python project layout and makes verification straightforward.

## Design decisions
- **Pure functions**: Each operation is a pure function with type hints and a docstring. This makes the module easy to import and test.
- **Division‑by‑zero handling**: `divide` raises a `ZeroDivisionError` with a clear message. This mirrors Python's built‑in behavior but provides a custom message for better diagnostics.
- **Testing framework**: `unittest` is chosen because it is part of the standard library, requires no external dependencies, and integrates well with CI pipelines.
- **Edge‑case coverage**: Tests include typical cases, negative numbers, zero, and the expected exception for division by zero.

---

## Step 1: calculator.py
### Why
The core arithmetic functions must exist before any tests can be written. This step establishes the public API that the test suite will import.

### Design
- Provide four functions: `add`, `subtract`, `multiply`, `divide`.
- Use type hints (`float` for inputs and output) to support both integers and floats.
- Include docstrings describing behavior and parameters.
- In `divide`, check if the denominator is zero and raise `ZeroDivisionError` with a custom message.
- No external dependencies; pure Python.

### Template
```python
# calculator.py
"""Simple arithmetic calculator module.

Provides four basic operations: add, subtract, multiply, and divide.
The `divide` function raises a ZeroDivisionError when the divisor is zero.
"""
from __future__ import annotations

def add(a: float, b: float) -> float:
    """Return the sum of *a* and *b*.

    Args:
        a: First addend.
        b: Second addend.

    Returns:
        The arithmetic sum a + b.
    """
    return a + b


def subtract(a: float, b: float) -> float:
    """Return the difference of *a* and *b* (a - b).

    Args:
        a: Minuend.
        b: Subtrahend.

    Returns:
        The result of a - b.
    """
    return a - b


def multiply(a: float, b: float) -> float:
    """Return the product of *a* and *b*.

    Args:
        a: First factor.
        b: Second factor.

    Returns:
        The arithmetic product a * b.
    """
    return a * b


def divide(a: float, b: float) -> float:
    """Return the quotient of *a* divided by *b*.

    Args:
        a: Numerator.
        b: Denominator.

    Raises:
        ZeroDivisionError: If *b* is zero.

    Returns:
        The arithmetic quotient a / b.
    """
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero.")
    return a / b
```

### Validation
Run a quick import and sanity check:
```
python - <<'PY'
import calculator
assert calculator.add(2, 3) == 5
assert calculator.subtract(5, 2) == 3
assert calculator.multiply(4, 2.5) == 10.0
assert calculator.divide(10, 2) == 5.0
print('All basic checks passed')
PY
```

---

## Step 2: test_calculator.py
### Why
With the calculator module in place, we can now verify its correctness automatically. This step creates a test suite that the implementer (or CI) will run to confirm the functionality.

### Design
- Use the `unittest` framework.
- Create a `TestCalculator` class with separate test methods for each operation.
- Include tests for typical values, negative numbers, and zero.
- For division, add a test that asserts a `ZeroDivisionError` is raised when dividing by zero.
- The test file imports the `calculator` module from the same directory.

### Template
```python
# test_calculator.py
"""Unit tests for the calculator module.
"""
import unittest
import calculator

class TestCalculator(unittest.TestCase):
    def test_add(self):
        self.assertEqual(calculator.add(2, 3), 5)
        self.assertEqual(calculator.add(-1, 1), 0)
        self.assertAlmostEqual(calculator.add(0.1, 0.2), 0.3)

    def test_subtract(self):
        self.assertEqual(calculator.subtract(5, 2), 3)
        self.assertEqual(calculator.subtract(-1, -1), 0)
        self.assertAlmostEqual(calculator.subtract(0.3, 0.1), 0.2)

    def test_multiply(self):
        self.assertEqual(calculator.multiply(4, 2), 8)
        self.assertEqual(calculator.multiply(-3, 3), -9)
        self.assertAlmostEqual(calculator.multiply(0.5, 0.2), 0.1)

    def test_divide(self):
        self.assertEqual(calculator.divide(10, 2), 5)
        self.assertAlmostEqual(calculator.divide(1, 3), 1/3)
        self.assertRaises(ZeroDivisionError, calculator.divide, 5, 0)

if __name__ == '__main__':
    unittest.main()
```

### Validation
Run the test suite using the standard unittest runner:
```
python -m unittest test_calculator.py
```
The command should exit with a status code of 0 and report **OK**.
