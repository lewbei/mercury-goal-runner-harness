
def count_vowels(s: str) -> int:
    """
    Count the number of vowels (a, e, i, o, u) in the given string.
    The function is case‑insensitive.

    Args:
        s: Input string.

    Returns:
        Number of vowels in the string.

    Raises:
        TypeError: If `s` is not a string.
    """
    if not isinstance(s, str):
        raise TypeError("Input must be a string")
    vowels = set("aeiouAEIOU")
    return sum(1 for char in s if char in vowels)

if __name__ == "__main__":
    # Example usage demonstrating various edge cases
    examples = ["Hello World", "Python", "", "AEIOUaeiou"]
    for example in examples:
        print(f"Input: {example!r}")
        print(f"Vowel count: {count_vowels(example)}")
