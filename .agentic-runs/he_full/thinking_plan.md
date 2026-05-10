# Thinking Plan: Find Closest Elements

## Architecture
We will implement a single Python module `find_closest_elements.py` that provides the function `find_closest_elements`. The function will:
- Accept a list of floats (or ints) of length ≥ 2.
- Return a tuple `(a, b)` where `a <= b` and the absolute difference `|b - a|` is minimal among all pairs.
- Use a **sort‑then‑scan** approach: sort the input (O(n log n)), then scan adjacent elements (O(n)) to find the smallest gap. This yields overall O(n log n) time and O(1) extra space (aside from the sorted copy).

A separate test module `test_find_closest_elements.py` will verify correctness using Python’s built‑in `unittest` framework. The test file is not part of the contract’s `final_outputs` but serves as a validation step in the plan.

## Design decisions
| Decision | Options | Chosen | Why |
|----------|---------|--------|-----|
| Algorithmic approach | Brute‑force O(n²) pairwise comparison<br>Sort‑then‑scan O(n log n) | Sort‑then‑scan | Simpler code, deterministic O(n log n) performance, easy to reason about edge cases (duplicates) |
| Return order | Unordered pair (any order)<br>Sorted pair (smaller, larger) | Sorted pair | Matches docstring examples and provides deterministic output |
| Duplicate handling | Return first duplicate pair (e.g., (x, x))<br>Ignore duplicates and find next closest distinct values | Return duplicate pair | The contract’s examples include a duplicate case (`[1.0, 2.0, 3.0, 4.0, 5.0, 2.0] → (2.0, 2.0)`) |
| Input validation | Explicit runtime type checks and length guard<br>Assume correct input per contract | Assume correct input, but raise `ValueError` if length < 2 | Keeps implementation lightweight while still providing a clear error for misuse |
| Testing framework | `unittest` (standard library)<br>`pytest` (third‑party) | `unittest` | No external dependencies required, aligns with the repository’s minimal setup |

---

## Step 1: find_closest_elements.py

### Why
This file implements the core functionality required by the contract. It must be correct before any other files (e.g., tests) can be useful.

### Design
1. **Input** – a list of numbers (`List[float]`). The function will not mutate the original list.
2. **Algorithm** –
   - Create a sorted copy of the list.
   - Initialise `best_pair` with the first two elements and `best_diff` with their absolute difference.
   - Iterate over the sorted list from index 1 to `len(sorted_numbers) - 1`, comparing each adjacent pair.
   - If a smaller difference is found, update `best_pair` and `best_diff`.
   - Return `best_pair` (already sorted because the list is sorted).
3. **Edge cases** –
   - List length < 2 → raise `ValueError`.
   - Duplicate numbers → the difference becomes `0.0`, which is the minimal possible; the algorithm will return that pair.
4. **Complexity** – O(n log n) time, O(n) additional space for the sorted copy.
5. **Signature & docstring** – full type hints, clear description, examples, and error description.

### Template
```python
# find_closest_elements.py
from typing import List, Tuple


def find_closest_elements(numbers: List[float]) -> Tuple[float, float]:
    """Return the two numbers in *numbers* that are closest to each other.

    The function expects a list of at least two numeric values (int or float).
    It returns a tuple ``(a, b)`` where ``a <= b`` and the absolute difference
    ``|b - a|`` is minimal among all possible pairs.

    If multiple pairs have the same minimal difference, the pair that appears
    first in the sorted order is returned. Duplicate values are allowed; in that
    case the function will return ``(x, x)`` for the duplicated value ``x``.

    Raises
    ------
    ValueError
        If ``numbers`` contains fewer than two elements.

    Examples
    --------
    >>> find_closest_elements([1.0, 2.0, 3.0, 4.0, 5.0, 2.2])
    (2.0, 2.2)
    >>> find_closest_elements([1.0, 2.0, 3.0, 4.0, 5.0, 2.0])
    (2.0, 2.0)
    """
    if len(numbers) < 2:
        raise ValueError("At least two numbers are required to find the closest pair.")

    # Create a sorted copy; sorting ensures that the closest pair must be adjacent.
    sorted_numbers = sorted(numbers)

    # Initialise with the first adjacent pair.
    best_pair = (sorted_numbers[0], sorted_numbers[1])
    best_diff = abs(sorted_numbers[1] - sorted_numbers[0])

    # Scan adjacent pairs for a smaller difference.
    for i in range(1, len(sorted_numbers) - 1):
        a, b = sorted_numbers[i], sorted_numbers[i + 1]
        diff = b - a  # b >= a because the list is sorted
        if diff < best_diff:
            best_diff = diff
            best_pair = (a, b)
            # Early exit if we hit zero difference – cannot get better.
            if best_diff == 0.0:
                break

    return best_pair


if __name__ == "__main__":
    # Simple manual test when the module is executed directly.
    import sys
    # Expect a space‑separated list of numbers on the command line.
    if len(sys.argv) < 2:
        print("Usage: python find_closest_elements.py <num1> <num2> ...")
        sys.exit(1)
    try:
        input_numbers = [float(arg) for arg in sys.argv[1:]]
    except ValueError:
        print("All arguments must be numeric.")
        sys.exit(1)
    result = find_closest_elements(input_numbers)
    print(f"Closest pair: {result}")
```

### Validation
```bash
# 1. Run a quick manual check:
python find_closest_elements.py 1.0 2.0 3.0 4.0 5.0 2.2
# Expected output: Closest pair: (2.0, 2.2)

# 2. Run the unit tests defined in Step 2 (after they are created):
python -m unittest test_find_closest_elements.py
```

---

## Step 2: test_find_closest_elements.py

### Why
A test suite provides automated verification that the implementation satisfies the contract’s examples and handles edge cases correctly before the file is considered done.

### Design
We will use the standard library `unittest` module. The test class will contain:
- `test_example_cases` – verifies the two examples from the contract docstring.
- `test_duplicate_values` – ensures a duplicate pair is returned when present.
- `test_unsorted_input` – confirms the function works regardless of input order.
- `test_invalid_input` – checks that a `ValueError` is raised for lists with fewer than two elements.
- `test_float_precision` – a case with very close floating‑point numbers to ensure the algorithm does not suffer from rounding errors.

All tests are deterministic and do not require external resources.

### Template
```python
# test_find_closest_elements.py
import unittest
from find_closest_elements import find_closest_elements

class TestFindClosestElements(unittest.TestCase):
    def test_example_cases(self):
        self.assertEqual(
            find_closest_elements([1.0, 2.0, 3.0, 4.0, 5.0, 2.2]),
            (2.0, 2.2)
        )
        self.assertEqual(
            find_closest_elements([1.0, 2.0, 3.0, 4.0, 5.0, 2.0]),
            (2.0, 2.0)
        )

    def test_duplicate_values(self):
        self.assertEqual(
            find_closest_elements([10.0, 10.0, 5.0, 7.0]),
            (10.0, 10.0)
        )

    def test_unsorted_input(self):
        self.assertEqual(
            find_closest_elements([5.5, 1.1, 3.3, 2.2, 4.4]),
            (2.2, 3.3)
        )

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            find_closest_elements([1.0])
        with self.assertRaises(ValueError):
            find_closest_elements([])

    def test_float_precision(self):
        # Numbers that differ by a very small epsilon.
        numbers = [0.0, 1e-9, 1e-8, 1e-7]
        self.assertEqual(
            find_closest_elements(numbers),
            (0.0, 1e-9)
        )

if __name__ == "__main__":
    unittest.main()
```

### Validation
```bash
# Run the test suite:
python -m unittest test_find_closest_elements.py
# All tests should pass (exit code 0).
```

---

## Summary
The plan consists of two concrete steps. Step 1 provides a complete, well‑documented implementation of `find_closest_elements`. Step 2 supplies a thorough unit‑test suite that validates the implementation against the contract’s examples, edge cases, and error handling. Following the validation commands will confirm that the solution meets the `done_criteria` defined in `goal_contract.json`.
