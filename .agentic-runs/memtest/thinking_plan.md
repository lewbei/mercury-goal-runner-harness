# Thinking Plan: Email Validator

## Architecture
We need a single, self‑contained Python module that provides a clear, reusable function for email validation. The module will expose one public function `is_valid_email(email: Optional[str]) -> bool`. All logic lives in this file; no external configuration or additional modules are required. This keeps the implementation simple, easy to test, and aligns with the contract’s `final_outputs` of a single file `validate_email.py`.

## Design decisions
| Decision | Options | Chosen | Why |
|----------|---------|--------|-----|
| Validation approach | 1. Use Python's `email.utils.parseaddr` (basic parsing). 2. Use a handcrafted regular expression. 3. Use third‑party library (e.g., `email-validator`). | Regular expression | A regex gives deterministic, fast validation without external dependencies. It can enforce a reasonable subset of RFC‑5322 while staying lightweight for an "EASY" task. |
| Error handling for non‑string input | 1. Raise `TypeError`. 2. Return `False`. | Return `False` | The goal is to provide a simple boolean check. Returning `False` for invalid types keeps the API easy to use in conditional statements and avoids forcing callers to handle exceptions. |
| Whitespace handling | 1. Reject whitespace‑containing strings. 2. Strip surrounding whitespace before validation. | Strip whitespace | Users often paste email addresses with accidental spaces. Stripping improves usability while still rejecting internal spaces, which are invalid. |

---

## Step 1: validate_email.py

### Why
This is the sole artifact required by the contract. Creating it first establishes the core functionality; all subsequent validation steps depend on this file existing.

### Design
* **Signature** – `def is_valid_email(email: Optional[str]) -> bool:` – accepts a string or `None` and returns a boolean.
* **Docstring** – explains parameters, return value, and design notes.
* **Implementation** – uses a compiled regular expression that checks for a non‑empty local part, an `@` symbol, and a domain with at least one dot. The function:
  1. Verifies the input is a `str`.
  2. Strips surrounding whitespace.
  3. Returns `False` for empty strings.
  4. Returns the result of `fullmatch` against the regex.
* **Error handling** – no exceptions are raised for invalid inputs; the function simply returns `False`.
* **Testing** – a small validation block is provided in the docstring and can be run via `python -m validate_email`.

### Template
```python
import re
from typing import Optional

# Regular expression pattern for a simple email validation.
_EMAIL_REGEX = re.compile(
    r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
)

def is_valid_email(email: Optional[str]) -> bool:
    """
    Validate whether the provided string is a syntactically valid email address.

    Parameters
    ----------
    email : Optional[str]
        The email address to validate. If ``None`` or not a string, the function
        returns ``False``.

    Returns
    -------
    bool
        ``True`` if ``email`` matches the email pattern, ``False`` otherwise.

    Notes
    -----
    - The validation uses a regular expression that checks for a local part,
      an ``@`` symbol, and a domain part with at least one dot.
    - This is a syntactic check only; it does not verify that the address
      actually exists or can receive mail.
    - The function deliberately returns ``False`` for non‑string inputs instead
      of raising an exception, to keep the API simple for callers.
    """
    if not isinstance(email, str):
        return False
    # Strip surrounding whitespace to avoid false negatives.
    email = email.strip()
    if not email:
        return False
    return _EMAIL_REGEX.fullmatch(email) is not None

# Simple sanity‑check when run as a script.
if __name__ == "__main__":
    test_cases = {
        "test@example.com": True,
        "user.name+tag@sub.domain.co": True,
        "invalid-email": False,
        "@missinglocal.com": False,
        "missingdomain@": False,
        "": False,
        None: False,
        "   spaced@example.com   ": True,
    }
    for email, expected in test_cases.items():
        result = is_valid_email(email)
        assert result == expected, f"Failed for {email!r}: expected {expected}, got {result}"
    print("All sanity checks passed.")
```

### Validation
To verify the implementation before proceeding:

```bash
# 1. Run the built‑in sanity checks
python validate_email.py

# 2. Import the function in an interactive session
python - <<'PY'
from validate_email import is_valid_email
assert is_valid_email('alice@example.com') is True
assert is_valid_email('bad@@example.com') is False
assert is_valid_email('') is False
assert is_valid_email(None) is False
print('Manual checks passed')
PY
```

If the script exits without assertion errors and prints the expected messages, the step is considered successful.
---
