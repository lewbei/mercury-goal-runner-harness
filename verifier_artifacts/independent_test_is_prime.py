"""
Independent verifier test for is_prime function.
This test is produced by the verifier-generator agent, not the worker agent,
and tests the function behavior without relying on the solution's own test suite.
"""
import sys
import traceback


def run_independent_test():
    """Run behavioral assertions on is_prime independent from solution tests."""
    errors = []

    # Try to import the solution
    try:
        from is_prime import is_prime
    except ImportError as e:
        print(f"FAIL: Could not import is_prime: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"FAIL: Unexpected error importing is_prime: {e}")
        sys.exit(1)

    # --- Assertion 1: Known primes ---
    known_primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 97]
    for n in known_primes:
        try:
            result = is_prime(n)
            if result is not True:
                errors.append(f"is_prime({n}) returned {result}, expected True")
        except Exception as e:
            errors.append(f"is_prime({n}) raised exception: {e}")

    # --- Assertion 2: Known composites ---
    known_composites = [0, 1, 4, 6, 8, 9, 10, 16, 20, 24, 100]
    for n in known_composites:
        try:
            result = is_prime(n)
            if result is not False:
                errors.append(f"is_prime({n}) returned {result}, expected False")
        except Exception as e:
            errors.append(f"is_prime({n}) raised exception: {e}")

    # --- Assertion 3: Negative numbers are not prime ---
    for n in [-1, -5, -10, -100]:
        try:
            result = is_prime(n)
            if result is not False:
                errors.append(f"is_prime({n}) returned {result}, expected False for negative numbers")
        except Exception as e:
            errors.append(f"is_prime({n}) raised exception: {e}")

    # --- Assertion 4: TypeError for non-int inputs ---
    for bad_input in [3.14, "13", None, [2], 2.0]:
        try:
            is_prime(bad_input)
            errors.append(f"is_prime({bad_input!r}) did not raise TypeError")
        except TypeError:
            pass  # Expected
        except Exception as e:
            errors.append(f"is_prime({bad_input!r}) raised {type(e).__name__}, expected TypeError")

    # --- Report ---
    if errors:
        print(f"FAIL: {len(errors)} assertion(s) failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("PASS: All independent verifier assertions passed.")
        print(f"  - {len(known_primes)} known primes checked")
        print(f"  - {len(known_composites)} known composites checked")
        print(f"  - 4 negative numbers checked")
        print(f"  - 5 invalid types checked")
        sys.exit(0)


if __name__ == "__main__":
    run_independent_test()
