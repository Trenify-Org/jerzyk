"""Tests for tabela.py: confidence intervals in the results tables.

  python3 -m unittest test_tabela
"""
import unittest

from tabela import komorka, model_index, uzupelnij_n, wilson


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


class TestUzupelnijN(unittest.TestCase):
    def test_older_results_get_n_from_document_counts(self):
        p = {"adm_real.termin": {"trafnosc": 0.714}, "sad_real.rodzaj": {"trafnosc": 0.989, "n": 89}}
        out = uzupelnij_n(p, {"adm_real": 56, "sad_real": 90})
        self.assertEqual(out["adm_real.termin"]["n"], 56)
        self.assertEqual(out["sad_real.rodzaj"]["n"], 89)  # stored n wins
        self.assertNotIn("n", p["adm_real.termin"])        # input not modified

    def test_unknown_domain_stays_without_n(self):
        self.assertNotIn("n", uzupelnij_n({"x.q": {"trafnosc": 0.5}}, {})["x.q"])


class TestModelIndex(unittest.TestCase):
    def test_yaml_with_both_results(self):
        y = model_index(0.8642, 0.8657)
        self.assertTrue(y.startswith("model-index:\n- name: jerzyk-1.0\n"))
        self.assertIn("type: trenify/jerzyk-bench", y)
        self.assertIn("value: 86.4\n", y)
        self.assertIn("value: 86.6\n", y)
        self.assertEqual(y.count("- task:"), 2)


if __name__ == "__main__":
    unittest.main()
