# Thinking Plan for Calculator Module

## Design Reasoning
- The goal is to create a simple Python module `calculator.py` that provides four arithmetic functions: `add`, `subtract`, `multiply`, and `divide`.
- The `divide` function must include basic error handling for division by zero, raising a `ValueError` with a clear message.
- A test suite `test_calculator.py` should be created using Python's built‑in `unittest` framework. It will test each operation for correctness and also verify that division by zero raises the expected exception.
- Both files will be placed in the run directory `.agentic-runs/qrspi_final/`.

## Code Templates

### calculator.py
```python
# calculator.py

def add(a, b):
    """Return the sum of a and b."""
    return a + b


def subtract(a, b):
    """Return the difference of a and b (a - b)."""
    return a - b


def multiply(a, b):
    """Return the product of a and b."""
    return a * b


def divide(a, b):
    """Return the quotient of a divided by b. Raise ValueError on division by zero."""
    if b == 0:
        raise ValueError("Division by zero is not allowed.")
    return a / b
```

### test_calculator.py
```python
# test_calculator.py
import unittest
import calculator

class TestCalculator(unittest.TestCase):
    def test_add(self):
        self.assertEqual(calculator.add(2, 3), 5)
        self.assertEqual(calculator.add(-1, 1), 0)

    def test_subtract(self):
        self.assertEqual(calculator.subtract(5, 2), 3)
        self.assertEqual(calculator.subtract(0, 5), -5)

    def test_multiply(self):
        self.assertEqual(calculator.multiply(4, 3), 12)
        self.assertEqual(calculator.multiply(-2, 3), -6)

    def test_divide(self):
        self.assertEqual(calculator.divide(10, 2), 5)
        self.assertAlmostEqual(calculator.divide(7, 3), 7/3)

    def test_divide_by_zero(self):
        with self.assertRaises(ValueError):
            calculator.divide(10, 0)

if __name__ == '__main__':
    unittest.main()
```

---

The next step will be to implement the files from the above templates and log each action.
