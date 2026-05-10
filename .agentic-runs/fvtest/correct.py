#@ Requires(lambda s: s is not None, "Input must not be None")
def correct(text):
    if text is None:
        raise ValueError("None not allowed")
    return len(text)
