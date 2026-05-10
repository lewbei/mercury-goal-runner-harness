# below_zero.py
from typing import List


def below_zero(operations: List[int]) -> bool:
    """Return ``True`` if the cumulative balance ever falls below zero.

    The account starts at a balance of zero. Each element of ``operations`` is an
    integer representing a deposit (positive) or withdrawal (negative). The function
    processes the list sequentially, updating the balance after each operation. If at
    any point the balance becomes negative, ``True`` is returned; otherwise ``False``.

    Args:
        operations: A list of integer amounts. Positive values deposit money, negative
            values withdraw money.

    Returns:
        ``True`` if the balance is negative at any point, ``False`` otherwise.

    Raises:
        TypeError: If ``operations`` is not a list or contains non‑integer items.
    """
    # Validate that the input is a list
    if not isinstance(operations, list):
        raise TypeError("operations must be a list of integers")

    balance = 0
    for idx, op in enumerate(operations):
        # Validate each element is an integer
        if not isinstance(op, int):
            raise TypeError(f"operation at index {idx} is not an integer: {op!r}")
        balance += op
        if balance < 0:
            return True
    return False
