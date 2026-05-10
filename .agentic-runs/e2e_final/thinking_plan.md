# Thinking Plan: Vowel Counter

## Architecture
A single Python file (`count_vowels.py`) is sufficient for this simple task. The file will expose a reusable function `count_vowels` and a `__main__` block for demonstration. No additional modules or configuration files are needed.

## Design decisions
| Decision | Options | Chosen | Why |
|----------|---------|--------|-----|
| Function signature | `def count_vowels(s):` (no type hints) vs `def count_vowels(s: str) -> int:` (type hints) | `def count_vowels(s: str) -> int:` | Type hints improve readability and static analysis without adding runtime cost. |
| Vowel set handling | Hard‑coded string `'aeiouAEIOU'` vs dynamically generated with `str.lower()` | Hard‑coded set | Direct membership test on a set is O(1) and avoids extra string manipulation. |
| Error handling | Return `0` for non‑string input vs raise `TypeError` | Raise `TypeError` | Explicit errors surface misuse early and match Pythonic expectations. |
| Demonstration output | Print a single example vs multiple examples | Multiple examples | Shows function works across edge cases (empty string, mixed case, all vowels). |

---

## Step 1: count_vowels.py

### Why
The contract requires a Python function that counts vowels in a string. This file implements the function and includes a demo `__main__` block to verify behavior.

### Design
The implementation iterates over the input string, checking each character against a pre‑computed set of vowel characters (both lower‑ and upper‑case). It counts matches using a generator expression. The function validates its argument type and raises a `TypeError` for non‑string inputs. The `__main__` block runs a few example strings and prints both the input and the vowel count, guaranteeing at least two lines of output per example.

### Template
```python

def count_vowels(s: str) -> int:
    """
    Count the number of vowels (a, e, i, o, u) in the given string.
    The function is case‑insensitive.

    Args:
        s: Input string.

    Returns:
        Number of vowels in the string.

    Raises:
        TypeError: If `s` is not a string.
    """
    if not isinstance(s, str):
        raise TypeError("Input must be a string")
    vowels = set("aeiouAEIOU")
    return sum(1 for char in s if char in vowels)

if __name__ == "__main__":
    # Example usage demonstrating various edge cases
    examples = ["Hello World", "Python", "", "AEIOUaeiou"]
    for example in examples:
        print(f"Input: {example!r}")
        print(f"Vowel count: {count_vowels(example)}")
```

### Validation
Run the file with:
```
python count_vowels.py
```
You should see at least two lines of output for each example, confirming the function works and the script produces output.
