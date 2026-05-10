"""
reverse_string.py

Provides a function to reverse a string.
"""

def reverse_string(s: str) -> str:
    """
    Return the reverse of the input string.

    Parameters
    ----------
    s : str
        The string to reverse.

    Returns
    -------
    str
        The reversed string.

    Raises
    ------
    TypeError
        If `s` is not a string.
    """
    if not isinstance(s, str):
        raise TypeError(f"Expected a string, got {type(s).__name__}")
    # Using Python slicing which is efficient and concise
    return s[::-1]

if __name__ == "__main__":
    # Simple manual test
    test_str = "hello"
    print(f"Input: {test_str}")
print(f"Output: {reverse_string(test_str)}")
