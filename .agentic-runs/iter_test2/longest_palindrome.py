"""Longest palindromic substring finder with formal annotations."""
#@ Requires(lambda s: isinstance(s, str), "Input must be a string")
#@ Ensures(lambda result, s: result is not None, "Result must not be None")
#@ Ensures(lambda result, s: result == result[::-1], "Result must be a palindrome")
#@ Ensures(lambda result, s: len(result) <= len(s), "Result cannot be longer than input")

def longest_palindrome(s: str) -> str:
    """Return the longest palindromic substring in s."""
    if not isinstance(s, str):
        raise TypeError("Input must be a string")
    if len(s) <= 1:
        return s
    
    def expand(l: int, r: int) -> str:
        while l >= 0 and r < len(s) and s[l] == s[r]:
            l -= 1
            r += 1
        return s[l+1:r]
    
    longest = ""
    for i in range(len(s)):
        odd = expand(i, i)
        even = expand(i, i + 1)
        if len(odd) > len(longest):
            longest = odd
        if len(even) > len(longest):
            longest = even
    
    return longest
