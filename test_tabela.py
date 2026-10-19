"""Tests for tabela.py: confidence intervals in the results tables.

  python3 -m unittest test_tabela
"""
import unittest

from tabela import komorka, wilson


class TestWilson(unittest.TestCase):
    def test_known_value(self):
        lo, hi = wilson(0.696, 56)  # Jerzyk, pilność w prawdziwych obwieszczeniach
        self.assertAlmostEqual(lo, 0.566, places=2)
        self.assertAlmostEqual(hi, 0.801, places=2)

    def test_bounds(self):
        self.assertEqual(wilson(1.0, 89)[1], 1.0)
        self.assertEqual(wilson(0.0, 10)[0], 0.0)


class TestKomorka(unittest.TestCase):
    def test_with_n_shows_interval(self):
        self.assertEqual(komorka({"trafnosc": 0.696, "n": 56}, przedzial=True), "69.6 (57–80)")

    def test_without_n_or_interval(self):
        self.assertEqual(komorka({"trafnosc": 0.696}, przedzial=True), "69.6")
        self.assertEqual(komorka({"trafnosc": 0.696, "n": 56}), "69.6")


if __name__ == "__main__":
    unittest.main()
