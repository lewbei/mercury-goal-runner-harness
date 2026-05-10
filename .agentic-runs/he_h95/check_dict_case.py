# check_dict_case.py

def check_dict_case(d: dict) -> bool:
    """
    Given a dictionary, return True if all keys are strings in lower case
    or all keys are strings in upper case, else return False.
    The function should return False if the given dictionary is empty.

    Examples:
    >>> check_dict_case({"a": "apple", "b": "banana"})
    True
    >>> check_dict_case({"a": "apple", "A": "banana", "B": "banana"})
    False
    >>> check_dict_case({"a": "apple", 8: "banana", "a": "apple"})
    False
    >>> check_dict_case({"Name": "John", "Age": "36", "City": "Houston"})
    False
    >>> check_dict_case({"STATE": "NC", "ZIP": "12345"})
    True
    """
    # Validate that the input is a dictionary
    if not isinstance(d, dict):
        raise TypeError("Input must be a dictionary")

    # An empty dictionary does not satisfy the criteria
    if not d:
        return False

    # All keys must be strings
    if not all(isinstance(k, str) for k in d):
        return False

    # Determine if all keys are lower‑case or all are upper‑case
    all_lower = all(k.islower() for k in d)
    all_upper = all(k.isupper() for k in d)

    return all_lower or all_upper
