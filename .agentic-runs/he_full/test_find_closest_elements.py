# test_find_closest_elements.py
import unittest
from find_closest_elements import find_closest_elements

class TestFindClosestElements(unittest.TestCase):
    def test_example_cases(self):
        self.assertEqual(
            find_closest_elements([1.0, 2.0, 3.0, 4.0, 5.0, 2.2]),
            (2.0, 2.2)
        )
        self.assertEqual(
            find_closest_elements([1.0, 2.0, 3.0, 4.0, 5.0, 2.0]),
            (2.0, 2.0)
        )

    def test_duplicate_values(self):
        self.assertEqual(
            find_closest_elements([10.0, 10.0, 5.0, 7.0]),
            (10.0, 10.0)
        )

    def test_unsorted_input(self):
        self.assertEqual(
            find_closest_elements([5.5, 1.1, 3.3, 2.2, 4.4]),
            (2.2, 3.3)
        )

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            find_closest_elements([1.0])
        with self.assertRaises(ValueError):
            find_closest_elements([])

    def test_float_precision(self):
        # Numbers that differ by a very small epsilon.
        numbers = [0.0, 1e-9, 1e-8, 1e-7]
        self.assertEqual(
            find_closest_elements(numbers),
            (0.0, 1e-9)
        )

if __name__ == "__main__":
    unittest.main()
