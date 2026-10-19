"""Tests for scripts/rescore_results.py: re-scoring stored predictions after label corrections.

  python -m unittest tests.test_rescore_results
"""
import unittest

from scripts.rescore_results import domain_of, rescore

DETAILS = [
    {"id": "adm_real-000", "q": "termin", "gold": True, "pred": True, "conf": 0.9},
    {"id": "adm_real-000", "q": "pilnosc", "gold": 2, "pred": 2, "conf": 0.8},
    {"id": "adm_real-001", "q": "termin", "gold": True, "pred": False, "conf": 0.6},
    {"id": "adm_real-001", "q": "pilnosc", "gold": 0, "pred": 1, "conf": 0.7},
    {"id": "sad-test-003", "q": "rodzaj", "gold": "wyrok", "pred": "wyrok", "conf": 0.99},
]
TYPES = {"termin": "noul", "pilnosc": "score", "rodzaj": "choice"}


class TestDomainOf(unittest.TestCase):
    def test_real_and_generated_ids(self):
        self.assertEqual(domain_of("adm_real-008"), "adm_real")
        self.assertEqual(domain_of("sad_real-000"), "sad_real")
        self.assertEqual(domain_of("sad-test-003"), "sad")
        self.assertEqual(domain_of("email-dev-010"), "email")


class TestRescore(unittest.TestCase):
    def test_unchanged_gold_gives_the_same_accuracy(self):
        gold = {(d["id"], d["q"]): d["gold"] for d in DETAILS}
        r = rescore(DETAILS, gold, TYPES)
        self.assertEqual(r["questions"]["adm_real.termin"]["accuracy"], 0.5)
        self.assertEqual(r["questions"]["adm_real.termin"]["n"], 2)
        self.assertEqual(r["questions"]["sad.rodzaj"]["accuracy"], 1.0)

    def test_corrected_gold_changes_the_score(self):
        gold = {(d["id"], d["q"]): d["gold"] for d in DETAILS}
        gold[("adm_real-001", "pilnosc")] = 1   # the label was wrong, the model was right
        gold[("adm_real-001", "termin")] = False
        r = rescore(DETAILS, gold, TYPES)
        self.assertEqual(r["questions"]["adm_real.pilnosc"]["accuracy"], 1.0)
        self.assertEqual(r["questions"]["adm_real.termin"]["accuracy"], 1.0)
        self.assertEqual(r["details"][3]["gold"], 1)
        self.assertEqual(DETAILS[3]["gold"], 0)  # input not modified

    def test_brier_and_plus_minus_one(self):
        gold = {(d["id"], d["q"]): d["gold"] for d in DETAILS}
        q = rescore(DETAILS, gold, TYPES)["questions"]
        # p(True) = 0.9 for a correct True; p(True) = 0.4 when False was chosen with 0.6 against gold True
        self.assertAlmostEqual(q["adm_real.termin"]["brier"], ((1 - 0.9) ** 2 + (1 - 0.4) ** 2) / 2, places=3)
        self.assertEqual(q["adm_real.pilnosc"]["accuracy_pm1"], 1.0)

    def test_mean_over_domains_and_ece(self):
        gold = {(d["id"], d["q"]): d["gold"] for d in DETAILS}
        r = rescore(DETAILS, gold, TYPES)
        self.assertAlmostEqual(r["mean_accuracy_over_domains"], (0.5 + 1.0) / 2, places=3)  # adm_real 2/4, sad 1/1
        self.assertGreaterEqual(r["ece"], 0)


if __name__ == "__main__":
    unittest.main()
