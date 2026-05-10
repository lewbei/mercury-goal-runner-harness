def is_prime(n: int) -> bool:
    """
    Determine whether a given integer is a prime number.

    Parameters
    ----------
    n : int
        The integer to test. Must be a non‑negative integer.

    Returns
    -------
    bool
        True if ``n`` is prime, False otherwise.

    Raises
    ------
    TypeError
        If ``n`` is not an integer.
    """
    # Input type validation
    if not isinstance(n, int):
        raise TypeError(f"Expected int, got {type(n).__name__}")

    # Numbers less than 2 are not prime
    if n < 2:
        return False

    # Handle small primes directly
    if n in (2, 3):
        return True

    # Eliminate even numbers and multiples of 3 early
    if n % 2 == 0 or n % 3 == 0:
        return False

    # Check potential factors using 6k ± 1 optimization
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6

    return True
