def longest_palindrome(s: str) -> str:
    """
    Return the longest palindromic substring in the given string `s`.

    Parameters
    ----------
    s : str
        Input string to search for a palindrome.

    Returns
    -------
    str
        The longest palindromic substring. If multiple substrings of the same
        maximum length exist, the first one encountered (by leftmost start index)
        is returned. For an empty input string, an empty string is returned.

    Raises
    ------
    TypeError
        If `s` is not a string.
    """
    # Validate input type
    if not isinstance(s, str):
        raise TypeError(f"Expected a string, got {type(s).__name__}")

    # Edge case: empty string
    if not s:
        return ""

    # Private helper to expand around a centre and return palindrome length
    def _expand(left: int, right: int) -> int:
        while left >= 0 and right < len(s) and s[left] == s[right]:
            left -= 1
            right += 1
        # Length is right - left - 1 because left/right are now one step beyond the palindrome
        return right - left - 1

    start = 0  # start index of the longest palindrome found
    max_len = 1  # length of the longest palindrome found

    for i in range(len(s)):
        # Odd length palindrome (center at i)
        len1 = _expand(i, i)
        # Even length palindrome (center between i and i+1)
        len2 = _expand(i, i + 1)

        cur_len = max(len1, len2)
        if cur_len > max_len:
            max_len = cur_len
            # Compute new start index based on current centre i and palindrome length
            start = i - (cur_len - 1) // 2

    return s[start:start + max_len]
