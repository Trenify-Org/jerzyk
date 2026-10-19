"""Tests for jerzyk.py that need neither the model nor laya: calibration, domains and the Python API.

  python3 -m unittest test_jerzyk
"""
import json
import tempfile
import unittest
from pathlib import Path

from jerzyk import DOMAINS, Jerzyk, calibrate, load_calibration, resolve_domain
from tasks import questions


def _fake_answers(state, qs):
    """Fake laya output: the first option of every question with confidence 0.8."""
    answers = {}
    for qid, q in qs.items():
        if q["type"] == "noul":
            answers[qid] = {"type": "noul", "noul": 0.8, "confidence": 0.8}
        else:
            # choice: criteria is a dict {option: description}; score: a list of levels, keys "0".."n-1"
            opts = list(q["criteria"]) if q["type"] == "choice" else [str(i) for i in range(len(q["criteria"]))]
            rest = 0.2 / (len(opts) - 1)
            probs = {k: (0.8 if i == 0 else rest) for i, k in enumerate(opts)}
            a = {"type": q["type"], "probabilities": probs, "confidence": 0.8}
            a["choice" if q["type"] == "choice" else "score"] = opts[0]
            answers[qid] = a
    return {"answers": answers}


class _Agent:
    predict = staticmethod(_fake_answers)


def _jerzyk(temperatures=None):
    j = Jerzyk.__new__(Jerzyk)  # skip laya.load
    j.agent, j.temperatures = _Agent(), temperatures or {}
    return j


class TestCalibrate(unittest.TestCase):
    def test_temperature_1_changes_nothing(self):
        qs = questions("sad")
        self.assertEqual(calibrate(_fake_answers("x", qs), qs, {"noul": 1.0}), _fake_answers("x", qs))

    def test_temperature_flattens_noul(self):
        qs = questions("sad")
        a = calibrate(_fake_answers("x", qs), qs, {"noul": 2.0})["answers"]["termin"]
        self.assertLess(a["noul"], 0.8)
        self.assertGreater(a["noul"], 0.5)

    def test_probabilities_sum_to_1(self):
        qs = questions("email")
        res = calibrate(_fake_answers("x", qs), qs, {"choice": 2.6, "score": 3.5})
        for a in res["answers"].values():
            if "probabilities" in a:
                self.assertAlmostEqual(sum(a["probabilities"].values()), 1.0, places=3)


class TestLoadCalibration(unittest.TestCase):
    def test_reads_calibration_json(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "calibration.json").write_text(json.dumps({"choice": 2.6}))
            self.assertEqual(load_calibration(d), {"choice": 2.6})

    def test_falls_back_to_old_name(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "kalibracja.json").write_text(json.dumps({"noul": 1.75}))
            self.assertEqual(load_calibration(d), {"noul": 1.75})

    def test_missing_file_means_no_calibration(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(load_calibration(d), {})


class TestDomains(unittest.TestCase):
    def test_english_and_polish_names(self):
        for en, pl in (("court", "sad"), ("admin", "adm"), ("accounting", "ksieg"), ("email", "email")):
            self.assertEqual(resolve_domain(en), pl)
            self.assertEqual(resolve_domain(pl), pl)
        self.assertEqual(set(DOMAINS), {"court", "admin", "accounting", "email"})

    def test_unknown_domain_is_an_error(self):
        with self.assertRaises(ValueError):
            resolve_domain("medical")


class TestAsk(unittest.TestCase):
    def test_ask_matches_polish_alias(self):
        j = _jerzyk({"choice": 2.6, "noul": 1.75, "score": 3.5})
        for domain in ("sad", "adm", "ksieg", "email"):
            self.assertEqual(j.ask("text", domain=domain), j.zapytaj("text", domena=domain))

    def test_ask_accepts_english_domain(self):
        j = _jerzyk()
        self.assertEqual(j.ask("text", domain="accounting"), j.ask("text", domain="ksieg"))

    def test_ask_defaults_to_court(self):
        self.assertEqual(set(_jerzyk().ask("text")), set(questions("sad")))


if __name__ == "__main__":
    unittest.main()
