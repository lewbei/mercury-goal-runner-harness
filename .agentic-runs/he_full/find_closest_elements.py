# find_closest_elements.py
from typing import List, Tuple


def find_closest_elements(numbers: List[float]) -> Tuple[float, float]:
    """Return the two numbers in *numbers* that are closest to each other.

    The function expects a list of at least two numeric values (int or float).
    It returns a tuple ``(a, b)`` where ``a <= b`` and the absolute difference
    ``|b - a|`` is minimal among all possible pairs.

    If multiple pairs have the same minimal difference, the pair that appears
    first in the sorted order is returned. Duplicate values are allowed; in that
    case the function will return ``(x, x)`` for the duplicated value ``x``.

    Raises
    ------
    ValueError
        If ``numbers`` contains fewer than two elements.

    Examples
    --------
    >>> find_closest_elements([1.0, 2.0, 3.0, 4.0, 5.0, 2.2])
    (2.0, 2.2)
    >>> find_closest_elements([1.0, 2.0, 3.0, 4.0, 5.0, 2.0])
    (2.0, 2.0)
    """
    if len(numbers) < 2:
        raise ValueError("At least two numbers are required to find the closest pair.")

    # Create a sorted copy; sorting ensures that the closest pair must be adjacent.
    sorted_numbers = sorted(numbers)

    # Initialise with the first adjacent pair.
    best_pair = (sorted_numbers[0], sorted_numbers[1])
    best_diff = abs(sorted_numbers[1] - sorted_numbers[0])

    # Scan adjacent pairs for a smaller difference.
    for i in range(1, len(sorted_numbers) - 1):
        a, b = sorted_numbers[i], sorted_numbers[i + 1]
        diff = b - a  # b >= a because the list is sorted
        if diff < best_diff:
            best_diff = diff
            best_pair = (a, b)
            # Early exit if we hit zero difference – cannot get better.
            if best_diff == 0.0:
                break

    return best_pair


if __name__ == "__main__":
    # Simple manual test when the module is executed directly.
    import sys
    # Expect a space‑separated list of numbers on the command line.
    if len(sys.argv) < 2:
        print("Usage: python find_closest_elements.py <num1> <num2> ...")
        sys.exit(1)
    try:
        input_numbers = [float(arg) for arg in sys.argv[1:]]
    except ValueError:
        print("All arguments must be numeric.")
        sys.exit(1)
    result = find_closest_elements(input_numbers)
    print(f"Closest pair: {result}")
