# Strongest_Extension.py
"""Implementation of the Strongest_Extension function.

The function selects the *strongest* extension from a list based on the
formula ``strength = #uppercase letters - #lowercase letters``.  If multiple
extensions share the highest strength, the first one in the list is chosen.

The result is returned as ``"{class_name}.{strongest_extension}"``.

Raises:
    ValueError: If ``extensions`` is empty.
    TypeError: If ``class_name`` is not a string or any element of ``extensions``
               is not a string.
"""
from __future__ import annotations


def _strength(ext: str) -> int:
    """Return the strength of *ext* as ``uppercase - lowercase``.

    Non‑alphabetic characters are ignored.
    """
    upper = sum(1 for ch in ext if ch.isalpha() and ch.isupper())
    lower = sum(1 for ch in ext if ch.isalpha() and ch.islower())
    return upper - lower


def Strongest_Extension(class_name: str, extensions: list[str]) -> str:
    """Select the strongest extension and return ``ClassName.StrongestExtension``.

    Parameters
    ----------
    class_name: str
        Name of the class to which the extension will be attached.
    extensions: list[str]
        List of candidate extension names.

    Returns
    -------
    str
        A string in the format ``"{class_name}.{strongest_extension}"``.

    Raises
    ------
    ValueError
        If ``extensions`` is empty.
    TypeError
        If ``class_name`` is not a string or any element of ``extensions`` is not a
        string.
    """
    if not isinstance(class_name, str):
        raise TypeError("class_name must be a string")
    if not isinstance(extensions, list):
        raise TypeError("extensions must be a list of strings")
    if len(extensions) == 0:
        raise ValueError("extensions list must contain at least one element")
    # Validate each extension is a string
    for i, ext in enumerate(extensions):
        if not isinstance(ext, str):
            raise TypeError(f"extension at index {i} is not a string")

    # Initialise with the first extension
    best_ext = extensions[0]
    best_strength = _strength(best_ext)

    # Iterate over the remaining extensions
    for ext in extensions[1:]:
        cur_strength = _strength(ext)
        if cur_strength > best_strength:
            best_ext = ext
            best_strength = cur_strength
        # If equal, keep the earlier one (do nothing)

    return f"{class_name}.{best_ext}"
