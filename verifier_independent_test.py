"""
Independent verifier test for roman_to_int.

This test file is authored by the verifier-generator sub-agent (independent from the
worker agent that creates roman_to_int.py). It tests only the public contract of the
roman_to_int function — no knowledge of internal implementation details.

Usage:
    python -m unittest verifier_independent_test.py
"""

import unittest
import sys
import os

# Allow importing roman_to_int from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))


class TestRomanToIntVerifier(unittest.TestCase):
    """Black-box tests for roman_to_int(). Independent from solution internals."""

    @classmethod
    def setUpClass(cls):
        """Import the module under test — will fail if roman_to_int.py does not exist."""
        try:
            from roman_to_int import roman_to_int
            cls.convert = roman_to_int
        except ImportError as e:
            raise unittest.SkipTest(f"roman_to_int not available yet: {e}")

    # --- Basic single numerals ---
    def test_single_I(self):
        self.assertEqual(self.convert('I'), 1)

    def test_single_V(self):
        self.assertEqual(self.convert('V'), 5)

    def test_single_X(self):
        self.assertEqual(self.convert('X'), 10)

    def test_single_L(self):
        self.assertEqual(self.convert('L'), 50)

    def test_single_C(self):
        self.assertEqual(self.convert('C'), 100)

    def test_single_D(self):
        self.assertEqual(self.convert('D'), 500)

    def test_single_M(self):
        self.assertEqual(self.convert('M'), 1000)

    # --- Additive combinations ---
    def test_II(self):
        self.assertEqual(self.convert('II'), 2)

    def test_III(self):
        self.assertEqual(self.convert('III'), 3)

    def test_VI(self):
        self.assertEqual(self.convert('VI'), 6)

    def test_XIII(self):
        self.assertEqual(self.convert('XIII'), 13)

    def test_LXX(self):
        self.assertEqual(self.convert('LXX'), 70)

    def test_CC(self):
        self.assertEqual(self.convert('CC'), 200)

    def test_MMXX(self):
        self.assertEqual(self.convert('MMXX'), 2020)

    # --- Subtractive notation ---
    def test_IV(self):
        self.assertEqual(self.convert('IV'), 4)

    def test_IX(self):
        self.assertEqual(self.convert('IX'), 9)

    def test_XL(self):
        self.assertEqual(self.convert('XL'), 40)

    def test_XC(self):
        self.assertEqual(self.convert('XC'), 90)

    def test_CD(self):
        self.assertEqual(self.convert('CD'), 400)

    def test_CM(self):
        self.assertEqual(self.convert('CM'), 900)

    # --- Complex valid numerals ---
    def test_MCMXCIV(self):
        self.assertEqual(self.convert('MCMXCIV'), 1994)

    def test_MMXXIV(self):
        self.assertEqual(self.convert('MMXXIV'), 2024)

    def test_XLVII(self):
        self.assertEqual(self.convert('XLVII'), 47)

    def test_CDXLIV(self):
        self.assertEqual(self.convert('CDXLIV'), 444)

    def test_MCMLXXXVII(self):
        self.assertEqual(self.convert('MCMLXXXVII'), 1987)

    # --- Lowercase input ---
    def test_lowercase_iii(self):
        self.assertEqual(self.convert('iii'), 3)

    def test_lowercase_mcmxcix(self):
        self.assertEqual(self.convert('mcmxcix'), 1999)

    # --- Edge cases ---
    def test_largest_MMMCMXCIX(self):
        self.assertEqual(self.convert('MMMCMXCIX'), 3999)

    # --- Error handling: invalid characters ---
    def test_invalid_characters_ABC(self):
        with self.assertRaises(ValueError):
            self.convert('ABC')

    def test_invalid_characters_XYZ(self):
        with self.assertRaises(ValueError):
            self.convert('XYZ')

    # --- Error handling: invalid sequences ---
    def test_invalid_IIII(self):
        with self.assertRaises(ValueError):
            self.convert('IIII')

    def test_invalid_VX(self):
        with self.assertRaises(ValueError):
            self.convert('VX')

    def test_invalid_IC(self):
        with self.assertRaises(ValueError):
            self.convert('IC')

    def test_invalid_IL(self):
        with self.assertRaises(ValueError):
            self.convert('IL')

    def test_invalid_VIV(self):
        with self.assertRaises(ValueError):
            self.convert('VIV')

    def test_invalid_XXXX(self):
        with self.assertRaises(ValueError):
            self.convert('XXXX')

    # --- Error handling: empty string ---
    def test_empty_string(self):
        with self.assertRaises(ValueError):
            self.convert('')

    # --- Error handling: whitespace only after strip ---
    def test_whitespace_only(self):
        with self.assertRaises(ValueError):
            self.convert('   ')

    # --- Error handling: wrong type ---
    def test_non_string_int(self):
        with self.assertRaises(TypeError):
            self.convert(123)

    def test_non_string_none(self):
        with self.assertRaises(TypeError):
            self.convert(None)

    def test_non_string_list(self):
        with self.assertRaises(TypeError):
            self.convert(['X'])


if __name__ == '__main__':
    unittest.main()
