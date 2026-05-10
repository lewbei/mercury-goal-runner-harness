"""is_perfect_square.py

Utility module that provides a function to check whether a given integer is a perfect square.
"""

import math
from typing import Any

#@ Requires(lambda n: isinstance(n, int), "Input must be an integer")
#@ Ensures(lambda result, n: isinstance(result, bool), "Result must be a boolean")
def is_perfect_square(n: int) -> bool:
    """Return ``True`` if *n* is a perfect square, otherwise ``False``.

    Args:
        n: Integer to test. Negative numbers are not perfect squares.

    Returns:
        ``True`` if *n* is a perfect square, ``False`` otherwise.
    """
    if n < 0:
        return False
    # Use integer square root to avoid floating‑point errors.
    root = math.isqrt(n)
    return root * root == n


if __name__ == "__main__":
    # Simple manual test suite – prints one line per number (>=2 lines).
    test_numbers = [0, 1, 2, 4, 10, 16, -4]
    for num in test_numbers:
        print(f"{num}: {is_perfect_square(num)}")
