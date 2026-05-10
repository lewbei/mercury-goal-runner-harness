# Thinking Plan: Roman Numeral to Integer Converter

## Architecture

We will implement a single module `roman_to_int.py` that contains a function `roman_to_int` converting a Roman numeral string to an integer. To verify correctness, a separate test module `test_roman_to_int.py` will be created using Python's `unittest` framework. The conversion module does not depend on any external libraries and can be imported by the test module.

## Design decisions
| Decision | Options | Chosen | Why |
|---|---|---|---|
| Parsing algorithm | Iterate left‑to‑right with look‑ahead, or iterate right‑to‑left with previous value tracking | Right‑to‑left iteration with previous value tracking | Simpler handling of subtractive notation and fewer condition checks |
| Validation of numeral correctness | Simple character check only, or round‑trip validation (int → Roman → int) | Round‑trip validation | Catches illegal sequences such as `IIII` or `VX` that would otherwise produce a numeric value but are not valid Roman numerals |
| Error handling | Return `None` on invalid input, or raise exceptions | Raise `ValueError` (or `TypeError` for non‑string) | Makes failures explicit and aligns with typical Python library behavior |
| Testing framework | Manual assertions, `unittest`, `pytest` | `unittest` | Built‑in, no extra dependencies, sufficient for this small scope |

---

## Step 1: roman_to_int.py

### Why
The core conversion logic lives here. All subsequent steps (e.g., testing) depend on this module being present and correct.

### Design
We map each Roman character to its integer value. By iterating the string from right to left we can decide whether to add or subtract each value based on the previously seen (more significant) value. After computing the integer, we perform a round‑trip conversion back to a Roman numeral using a deterministic algorithm; if the round‑trip result differs from the original input, the input was not a valid Roman numeral (e.g., `IIII`). This approach ensures both syntactic and semantic validation.

### Template
```python
# roman_to_int.py

def roman_to_int(s: str) -> int:
    """
    Convert a Roman numeral string to an integer.

    Parameters
    ----------
    s : str
        Roman numeral string (e.g., "XIV").

    Returns
    -------
    int
        Integer representation of the Roman numeral.

    Raises
    ------
    TypeError
        If the input is not a string.
    ValueError
        If the input contains invalid characters or does not represent a valid Roman numeral.
    """
    # Type check
    if not isinstance(s, str):
        raise TypeError("Input must be a string")

    # Normalise input
    s = s.upper().strip()
    if not s:
        raise ValueError("Empty Roman numeral")

    # Mapping of single Roman numerals to their integer values
    roman_map = {
        'I': 1,
        'V': 5,
        'X': 10,
        'L': 50,
        'C': 100,
        'D': 500,
        'M': 1000,
    }

    # Validate characters
    if any(ch not in roman_map for ch in s):
        raise ValueError(f"Invalid Roman numeral character in '{s}'")

    total = 0
    prev_value = 0
    # Iterate from right to left
    for ch in reversed(s):
        value = roman_map[ch]
        if value < prev_value:
            total -= value
        else:
            total += value
            prev_value = value

    # Round‑trip validation to catch illegal sequences (e.g., "IIII", "VX")
    def int_to_roman(num: int) -> str:
        val_map = [
            (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
            (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
            (10, "X"), (9, "IX"), (5, "V"), (4, "IV"),
            (1, "I")
        ]
        result = []
        for val, symbol in val_map:
            while num >= val:
                result.append(symbol)
                num -= val
        return "".join(result)

    if int_to_roman(total) != s:
        raise ValueError(f"Invalid Roman numeral sequence: '{s}'")

    return total
```

### Validation
Run a few manual checks in a Python REPL:
```python
>>> from roman_to_int import roman_to_int
>>> roman_to_int('III')
3
>>> roman_to_int('IV')
4
>>> roman_to_int('MCMXCIV')
1994
>>> roman_to_int('IIII')
Traceback (most recent call last):
    ...
ValueError: Invalid Roman numeral sequence: 'IIII'
```

---

## Step 2: test_roman_to_int.py

### Why
Provides automated verification that `roman_to_int` works for typical cases, edge cases, and error handling.

### Design
We use the built‑in `unittest` module. Tests cover basic numerals, subtractive notation, the full example `MCMXCIV`, invalid characters, illegal repeat patterns, empty input, and non‑string input.

### Template
```python
# test_roman_to_int.py

import unittest
from roman_to_int import roman_to_int

class TestRomanToInt(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(roman_to_int('I'), 1)
        self.assertEqual(roman_to_int('II'), 2)
        self.assertEqual(roman_to_int('III'), 3)
        self.assertEqual(roman_to_int('IV'), 4)
        self.assertEqual(roman_to_int('V'), 5)
        self.assertEqual(roman_to_int('IX'), 9)
        self.assertEqual(roman_to_int('X'), 10)
        self.assertEqual(roman_to_int('XL'), 40)
        self.assertEqual(roman_to_int('L'), 50)
        self.assertEqual(roman_to_int('XC'), 90)
        self.assertEqual(roman_to_int('C'), 100)
        self.assertEqual(roman_to_int('CD'), 400)
        self.assertEqual(roman_to_int('D'), 500)
        self.assertEqual(roman_to_int('CM'), 900)
        self.assertEqual(roman_to_int('M'), 1000)
        self.assertEqual(roman_to_int('MCMXCIV'), 1994)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            roman_to_int('ABC')
        with self.assertRaises(ValueError):
            roman_to_int('IIII')
        with self.assertRaises(ValueError):
            roman_to_int('VX')
        with self.assertRaises(ValueError):
            roman_to_int('')
        with self.assertRaises(TypeError):
            roman_to_int(123)

if __name__ == '__main__':
    unittest.main()
```

### Validation
Run the test suite:
```
python -m unittest test_roman_to_int.py
```
All tests should pass without errors.
