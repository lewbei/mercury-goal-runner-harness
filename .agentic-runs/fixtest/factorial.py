
def factorial(n: int) -> int:
    """Return the factorial of a non‑negative integer n.

    Args:
        n: A non‑negative integer.

    Returns:
        The factorial of n.

    Raises:
        ValueError: If n is negative.
    """
    if n < 0:
        raise ValueError("Factorial is undefined for negative numbers")
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result
