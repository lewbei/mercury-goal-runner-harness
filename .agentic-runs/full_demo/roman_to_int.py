# roman_to_int.py

def roman_to_int(s: str) -> int:
    """
    Convert a Roman numeral string to an integer.

    Parameters
    ----------
    s : str
        Roman numeral string (e.g., "XIV").

    Returns
    -------
    int
        Integer representation of the Roman numeral.

    Raises
    ------
    TypeError
        If the input is not a string.
    ValueError
        If the input contains invalid characters or does not represent a valid Roman numeral.
    """
    # Type check
    if not isinstance(s, str):
        raise TypeError("Input must be a string")

    # Normalise input
    s = s.upper().strip()
    if not s:
        raise ValueError("Empty Roman numeral")

    # Mapping of single Roman numerals to their integer values
    roman_map = {
        'I': 1,
        'V': 5,
        'X': 10,
        'L': 50,
        'C': 100,
        'D': 500,
        'M': 1000,
    }

    # Validate characters
    if any(ch not in roman_map for ch in s):
        raise ValueError(f"Invalid Roman numeral character in '{s}'")

    total = 0
    prev_value = 0
    # Iterate from right to left
    for ch in reversed(s):
        value = roman_map[ch]
        if value < prev_value:
            total -= value
        else:
            total += value
            prev_value = value

    # Round‑trip validation to catch illegal sequences (e.g., "IIII", "VX")
    def int_to_roman(num: int) -> str:
        val_map = [
            (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
            (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
            (10, "X"), (9, "IX"), (5, "V"), (4, "IV"),
            (1, "I")
        ]
        result = []
        for val, symbol in val_map:
            while num >= val:
                result.append(symbol)
                num -= val
        return "".join(result)

    if int_to_roman(total) != s:
        raise ValueError(f"Invalid Roman numeral sequence: '{s}'")

    return total
