# numerical_letter_grade.py

def numerical_letter_grade(grades):
    """
    Convert a list of GPA values to letter grades.

    The mapping follows the table:
        GPA   | Letter grade
        4.0   | A+
        >3.7  | A
        >3.3  | A-
        >3.0  | B+
        >2.7  | B
        >2.3  | B-
        >2.0  | C+
        >1.7  | C
        >1.3  | C-
        >1.0  | D+
        >0.7  | D
        >0.0  | D-
        0.0   | E

    Example:
        >>> numerical_letter_grade([4.0, 3, 1.7, 2, 3.5])
        ['A+', 'B', 'C-', 'C', 'A-']

    Parameters
    ----------
    grades : iterable of float
        GPA values to convert. Each value must be between 0.0 and 4.0 inclusive.

    Returns
    -------
    list of str
        Corresponding letter grades.

    Raises
    ------
    ValueError
        If any GPA is outside the allowed range.
    """
    result = []
    for g in grades:
        # Validate GPA range
        if not isinstance(g, (int, float)):
            raise TypeError(f"GPA value {g!r} is not a number")
        if g < 0.0 or g > 4.0:
            raise ValueError(f"GPA {g} is out of range [0.0, 4.0]")

        # Exact matches first
        if g == 4.0:
            result.append("A+")
        elif g > 3.7:
            result.append("A")
        elif g > 3.3:
            result.append("A-")
        elif g > 3.0:
            result.append("B+")
        elif g > 2.7:
            result.append("B")
        elif g > 2.3:
            result.append("B-")
        elif g > 2.0:
            result.append("C+")
        elif g > 1.7:
            result.append("C")
        elif g > 1.3:
            result.append("C-")
        elif g > 1.0:
            result.append("D+")
        elif g > 0.7:
            result.append("D")
        elif g > 0.0:
            result.append("D-")
        else:  # g == 0.0
            result.append("E")
    return result

# Optional: simple sanity check when run as a script
if __name__ == "__main__":
    sample = [4.0, 3, 1.7, 2, 3.5]
    print("Input:", sample)
    print("Output:", numerical_letter_grade(sample))
