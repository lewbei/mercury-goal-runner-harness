# Thinking Plan: Implement check_dict_case

## Architecture
The solution consists of a single Python module `check_dict_case.py`. This module provides the `check_dict_case` function, which encapsulates all required logic. Keeping the implementation in one file simplifies testing and satisfies the goal contract, which expects only this file as output.

## Design decisions
- **Input validation**: The function checks that the argument is a dictionary and raises `TypeError` otherwise. This prevents silent failures when misused.
- **Empty dictionary**: Returning `False` for an empty dict follows the specification.
- **Key type enforcement**: All keys must be strings; any non‑string key leads to `False`.
- **Case detection**: We evaluate two mutually exclusive conditions:
  1. All keys are lower‑case (`str.islower()`).
  2. All keys are upper‑case (`str.isupper()`).
  If either condition holds, the function returns `True`; otherwise `False`.
- **Error handling**: The only explicit error is a `TypeError` for non‑dict inputs. All other invalid states return `False` as required.
- **Readability**: The implementation uses clear variable names and a comprehensive docstring with examples, aiding maintainability.

---

## Step 1: check_dict_case.py

### Why
This is the first and only step because the goal contract requires a single file `check_dict_case.py` that implements the function. No auxiliary files or modules are needed.

### Design
The module defines `check_dict_case` with full type hints, a detailed docstring, and explicit error handling. Edge cases such as empty dictionaries, non‑string keys, and mixed case keys are covered. The function is pure and has no side effects.

### Template
```python
# check_dict_case.py

def check_dict_case(d: dict) -> bool:
    """
    Given a dictionary, return True if all keys are strings in lower case
    or all keys are strings in upper case, else return False.
    The function should return False if the given dictionary is empty.

    Examples:
    >>> check_dict_case({"a": "apple", "b": "banana"})
    True
    >>> check_dict_case({"a": "apple", "A": "banana", "B": "banana"})
    False
    >>> check_dict_case({"a": "apple", 8: "banana", "a": "apple"})
    False
    >>> check_dict_case({"Name": "John", "Age": "36", "City": "Houston"})
    False
    >>> check_dict_case({"STATE": "NC", "ZIP": "12345"})
    True
    """
    # Validate that the input is a dictionary
    if not isinstance(d, dict):
        raise TypeError("Input must be a dictionary")

    # An empty dictionary does not satisfy the criteria
    if not d:
        return False

    # All keys must be strings
    if not all(isinstance(k, str) for k in d):
        return False

    # Determine if all keys are lower‑case or all are upper‑case
    all_lower = all(k.islower() for k in d)
    all_upper = all(k.isupper() for k in d)

    return all_lower or all_upper
```

### Validation
Run the following command to execute a quick sanity check of the implementation:

```bash
python - <<'PY'
from check_dict_case import check_dict_case

assert check_dict_case({"a": "apple", "b": "banana"}) is True
assert check_dict_case({"a": "apple", "A": "banana", "B": "banana"}) is False
assert check_dict_case({"a": "apple", 8: "banana", "a": "apple"}) is False
assert check_dict_case({"Name": "John", "Age": "36", "City": "Houston"}) is False
assert check_dict_case({"STATE": "NC", "ZIP": "12345"}) is True

print("All tests passed.")
PY
```

If the script prints `All tests passed.` the step is successful.
