# Thinking Plan: Implement Strongest_Extension

## Architecture
We only need a single Python module `Strongest_Extension.py` that provides the public function `Strongest_Extension`. The module is self‑contained and does not depend on any external libraries, which satisfies the goal contract’s simplicity and keeps the implementation portable across Python versions (>=3.7). No additional files (tests, utilities, or configuration) are required for the done criteria, but a validation command is provided to verify correctness.

## Design decisions
- **Strength calculation**: The strength of an extension is defined as `#uppercase letters - #lowercase letters`. Non‑alphabetic characters are ignored, matching the description in the contract. We implement this with a helper `_strength` that iterates over characters and uses `str.isupper()` / `str.islower()`.
- **Tie‑breaking**: When multiple extensions have the same strength we return the one that appears first in the input list. This is naturally achieved by iterating the list in order and only updating the best candidate when a strictly greater strength is found.
- **Error handling**: 
  - If `extensions` is empty we raise `ValueError` because there is no extension to select.
  - If any element of `extensions` is not a string we raise `TypeError` to surface misuse early.
  - `class_name` is expected to be a string; a `TypeError` is raised otherwise.
- **Complexity**: The algorithm runs in `O(N * L)` time where `N` is the number of extensions and `L` is the average length of an extension string. Memory usage is `O(1)` besides the input list.
- **Public API**: The module exposes only the `Strongest_Extension` function. The helper `_strength` is prefixed with an underscore to indicate it is private.

---

## Step 1: Strongest_Extension.py

### Why
This is the core artifact required by the goal contract. Implementing it first establishes the main functionality; no other files depend on it.

### Design
- **Signature**: `def Strongest_Extension(class_name: str, extensions: list[str]) -> str:`
- **Docstring**: Describes purpose, parameters, return value, and raised exceptions.
- **Error handling**: Checks for empty list, non‑string items, and non‑string `class_name`.
- **Algorithm**: Compute strength for each extension using `_strength`; keep track of the best extension and its strength; return `f"{class_name}.{best}"`.
- **Edge cases**: Handles extensions containing digits, punctuation, or other symbols by ignoring them in the strength calculation. Handles Unicode letters correctly because `str.isupper()`/`str.islower()` work with Unicode.

### Template
```python
# Strongest_Extension.py
"""Implementation of the Strongest_Extension function.

The function selects the *strongest* extension from a list based on the
formula ``strength = #uppercase letters - #lowercase letters``.  If multiple
extensions share the highest strength, the first one in the list is chosen.

The result is returned as ``"{class_name}.{strongest_extension}"``.

Raises:
    ValueError: If ``extensions`` is empty.
    TypeError: If ``class_name`` is not a string or any element of ``extensions``
               is not a string.
"""
from __future__ import annotations


def _strength(ext: str) -> int:
    """Return the strength of *ext* as ``uppercase - lowercase``.

    Non‑alphabetic characters are ignored.
    """
    upper = sum(1 for ch in ext if ch.isalpha() and ch.isupper())
    lower = sum(1 for ch in ext if ch.isalpha() and ch.islower())
    return upper - lower


def Strongest_Extension(class_name: str, extensions: list[str]) -> str:
    """Select the strongest extension and return ``ClassName.StrongestExtension``.

    Parameters
    ----------
    class_name: str
        Name of the class to which the extension will be attached.
    extensions: list[str]
        List of candidate extension names.

    Returns
    -------
    str
        A string in the format ``"{class_name}.{strongest_extension}"``.

    Raises
    ------
    ValueError
        If ``extensions`` is empty.
    TypeError
        If ``class_name`` is not a string or any element of ``extensions`` is not a
        string.
    """
    if not isinstance(class_name, str):
        raise TypeError("class_name must be a string")
    if not isinstance(extensions, list):
        raise TypeError("extensions must be a list of strings")
    if len(extensions) == 0:
        raise ValueError("extensions list must contain at least one element")
    # Validate each extension is a string
    for i, ext in enumerate(extensions):
        if not isinstance(ext, str):
            raise TypeError(f"extension at index {i} is not a string")

    # Initialise with the first extension
    best_ext = extensions[0]
    best_strength = _strength(best_ext)

    # Iterate over the remaining extensions
    for ext in extensions[1:]:
        cur_strength = _strength(ext)
        if cur_strength > best_strength:
            best_ext = ext
            best_strength = cur_strength
        # If equal, keep the earlier one (do nothing)

    return f"{class_name}.{best_ext}"
```

### Validation
Run the following inline test to verify the implementation matches the contract's test suite:

```bash
python - <<'PY'
from Strongest_Extension import Strongest_Extension

def check(candidate):
    # Simple cases
    assert candidate('Watashi', ['tEN', 'niNE', 'eIGHt8OKe']) == 'Watashi.eIGHt8OKe'
    assert candidate('Boku123', ['nani', 'NazeDa', 'YEs.WeCaNe', '32145tggg']) == 'Boku123.YEs.WeCaNe'
    assert candidate('__YESIMHERE', ['t', 'eMptY', 'nothing', 'zeR00', 'NuLl__', '123NoooneB321']) == '__YESIMHERE.NuLl__'
    assert candidate('K', ['Ta', 'TAR', 't234An', 'cosSo']) == 'K.TAR'
    assert candidate('__HAHA', ['Tab', '123', '781345', '-_-']) == '__HAHA.123'
    assert candidate('YameRore', ['HhAas', 'okIWILL123', 'WorkOut', 'Fails', '-_-']) == 'YameRore.okIWILL123'
    assert candidate('finNNalLLly', ['Die', 'NowW', 'Wow', 'WoW']) == 'finNNalLLly.WoW'
    # Edge cases
    assert candidate('_', ['Bb', '91245']) == '_.Bb'
    assert candidate('Sp', ['671235', 'Bb']) == 'Sp.671235'
    print('All assertions passed')

check(Strongest_Extension)
PY
```
If the script prints "All assertions passed" without raising an exception, the step is successful.

---
