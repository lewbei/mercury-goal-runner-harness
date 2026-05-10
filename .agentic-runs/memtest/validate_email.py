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
print("Ready.")
