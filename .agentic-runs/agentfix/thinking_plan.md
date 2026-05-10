# Thinking Plan: Reverse String Function

## Architecture
A single-file Python script that defines a function to reverse a string and includes a simple CLI for demonstration. No external dependencies are required; the script is self-contained.

## Design decisions
| Decision | Options | Chosen | Why |
|---|---|---|---|
| String reversal method | Manual loop, list reversal, slicing (`s[::-1]`) | Slicing | Slicing is concise, idiomatic, and O(n) with minimal code. |
| Error handling | Return empty string on non‑string input, raise `TypeError` | Raise `TypeError` | Explicitly informs the caller of misuse; silent failures are harder to debug. |
| Demonstration output | Print one example, print multiple examples | Print two examples | The contract requires at least two lines of output for validation. |

---

## Step 1: reverse_string.py

### Why
This is the only artifact needed to satisfy the goal contract. The function implements the core requirement, and the `__main__` block provides a simple validation that produces the required output.

### Design
- **Function**: `reverse_string(s: str) -> str` – returns the reversed string using slicing. Raises `TypeError` if the input is not a string.
- **CLI**: When run as a script, it demonstrates the function with two sample inputs and prints the results, ensuring at least two lines of output.
- **Error handling**: Input type is checked; a clear exception is raised for invalid usage.
- **Documentation**: Docstrings explain purpose, parameters, return value, and possible exceptions.

### Template
```python
"""reverse_string.py

Provides a simple function to reverse a string and a demonstration when executed as a script.
"""

from typing import Any


def reverse_string(s: str) -> str:
    """Return the reversed version of *s*.

    Parameters
    ----------
    s: str
        The string to reverse.

    Returns
    -------
    str
        The reversed string.

    Raises
    ------
    TypeError
        If *s* is not a string.
    """
    if not isinstance(s, str):
        raise TypeError(f"reverse_string expects a string, got {type(s).__name__}")
    # Using Python slicing which is efficient and concise.
    return s[::-1]


def _demo() -> None:
    """Run a simple demonstration printing two reversed strings."""
    examples = ["hello", "world"]
    for ex in examples:
        print(f"{ex!r} reversed is {reverse_string(ex)!r}")


if __name__ == "__main__":
    _demo()
```

### Validation
Run the script:
```bash
python reverse_string.py
```
Expected output (two lines):
```
'hello' reversed is 'olleh'
'world' reversed is 'dlrow'
```
The script must exit without error and produce at least two lines of output.

---
