"""
Independent verifier test for find_closest_elements.
Provenance: P2 (same workspace, independent agent, no internal knowledge).
Tests the public interface only — no mocking, no implementation inspection.
"""

import sys
import os

# Ensure the solution module is importable from the run directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from find_closest_elements import find_closest_elements


def test_basic_example():
    """Example from docstring: [1.0, 2.0, 3.0, 4.0, 5.0, 2.2] → (2.0, 2.2)"""
    result = find_closest_elements([1.0, 2.0, 3.0, 4.0, 5.0, 2.2])
    assert result == (2.0, 2.2), f"Expected (2.0, 2.2), got {result}"


def test_exact_duplicate():
    """Example from docstring: [1.0, 2.0, 3.0, 4.0, 5.0, 2.0] → (2.0, 2.0)"""
    result = find_closest_elements([1.0, 2.0, 3.0, 4.0, 5.0, 2.0])
    assert result == (2.0, 2.0), f"Expected (2.0, 2.0), got {result}"


def test_two_elements_only():
    """Minimal valid input returns the only pair."""
    result = find_closest_elements([5.0, 1.0])
    assert result == (1.0, 5.0), f"Expected (1.0, 5.0), got {result}"


def test_three_elements_mid_is_closest():
    """Closest pair is in the middle after sorting: [10, 1, 4] sorted → [1,4,10]; closest is (1,4)."""
    result = find_closest_elements([10.0, 1.0, 4.0])
    assert result == (1.0, 4.0), f"Expected (1.0, 4.0), got {result}"


def test_negative_numbers():
    """Negative values and a close pair across zero: [-5.0, -3.0, 0.0, 100.0] → (-5.0, -3.0)."""
    result = find_closest_elements([-5.0, -3.0, 0.0, 100.0])
    assert result == (-5.0, -3.0), f"Expected (-5.0, -3.0), got {result}"


def test_all_identical():
    """All identical values — the closest pair is the value with itself: [7.0, 7.0, 7.0] → (7.0, 7.0)."""
    result = find_closest_elements([7.0, 7.0, 7.0])
    assert result == (7.0, 7.0), f"Expected (7.0, 7.0), got {result}"


def test_output_order_invariant():
    """Output tuple always has smaller first, larger second."""
    result = find_closest_elements([100.0, 1.0, 99.0])
    a, b = result
    assert a <= b, f"Output not ordered: {result}"


def test_value_error_on_single_element():
    """A list with one element raises ValueError."""
    try:
        find_closest_elements([42.0])
        assert False, "Expected ValueError but no exception was raised"
    except ValueError:
        pass


def test_value_error_on_empty_list():
    """An empty list raises ValueError."""
    try:
        find_closest_elements([])
        assert False, "Expected ValueError but no exception was raised"
    except ValueError:
        pass


def test_first_pair_tie_breaking():
    """When two pairs have the same minimal difference, the first pair in sorted order wins.
       [1.0, 2.0, 3.0] → sorted: [1,2,3]; pairs: (1,2) diff=1, (2,3) diff=1 → first is (1,2)."""
    result = find_closest_elements([3.0, 1.0, 2.0])
    assert result == (1.0, 2.0), f"Expected (1.0, 2.0), got {result}"


def test_floats_with_fractional_differences():
    """Fractional differences are handled correctly."""
    result = find_closest_elements([0.1, 0.15, 0.3, 0.5])
    assert result == (0.1, 0.15), f"Expected (0.1, 0.15), got {result}"


def test_large_list_performance():
    """A larger list (1000 elements) completes without error (smoke test)."""
    large = [float(i) for i in range(1000, 0, -1)]
    result = find_closest_elements(large)
    assert result == (1.0, 2.0), f"Expected (1.0, 2.0) for reverse-range, got {result}"


def test_input_not_mutated():
    """The original list object is not mutated by the function."""
    original = [5.0, 1.0, 9.0, 3.0]
    snapshot = original[:]
    find_closest_elements(original)
    assert original == snapshot, f"Input list was mutated: {original} != {snapshot}"


if __name__ == "__main__":
    tests = [
        ("basic_example", test_basic_example),
        ("exact_duplicate", test_exact_duplicate),
        ("two_elements_only", test_two_elements_only),
        ("three_elements_mid_is_closest", test_three_elements_mid_is_closest),
        ("negative_numbers", test_negative_numbers),
        ("all_identical", test_all_identical),
        ("output_order_invariant", test_output_order_invariant),
        ("value_error_on_single_element", test_value_error_on_single_element),
        ("value_error_on_empty_list", test_value_error_on_empty_list),
        ("first_pair_tie_breaking", test_first_pair_tie_breaking),
        ("floats_with_fractional_differences", test_floats_with_fractional_differences),
        ("large_list_performance", test_large_list_performance),
        ("input_not_mutated", test_input_not_mutated),
    ]

    passed = 0
    failed = 0
    failures = []
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            failures.append((name, str(e)))
            print(f"  FAIL  {name}: {e}")
        except Exception as e:
            failed += 1
            failures.append((name, f"Exception: {type(e).__name__}: {e}"))
            print(f"  FAIL  {name}: {type(e).__name__}: {e}")

    print(f"\n{'=' * 40}")
    print(f"Total: {passed + failed}  |  Passed: {passed}  |  Failed: {failed}")
    if failures:
        print(f"Failures:")
        for name, msg in failures:
            print(f"  - {name}: {msg}")
    sys.exit(0 if failed == 0 else 1)
