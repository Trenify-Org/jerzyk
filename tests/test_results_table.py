"""Tests for scripts/results_table.py: confidence intervals in the results tables, and reading old and new result files.

  python3 -m unittest discover -s tests -t .
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import results_table
from scripts.results_table import (cell, document_counts, fill_n, latency_cell, model_index, normalise_file,
                                   read_hardware, wilson)


class TestWilson(unittest.TestCase):
    def test_known_value(self):
        lo, hi = wilson(0.696, 56)  # Jerzyk, urgency in real administrative notices
        self.assertAlmostEqual(lo, 0.566, places=2)
        self.assertAlmostEqual(hi, 0.801, places=2)

    def test_bounds(self):
        self.assertEqual(wilson(1.0, 89)[1], 1.0)
        self.assertEqual(wilson(0.0, 10)[0], 0.0)


class TestCell(unittest.TestCase):
    def test_with_n_shows_interval(self):
        self.assertEqual(cell({"accuracy": 0.696, "n": 56}, interval=True), "69.6 (57–80)")

    def test_without_n_or_interval(self):
        self.assertEqual(cell({"accuracy": 0.696}, interval=True), "69.6")
        self.assertEqual(cell({"accuracy": 0.696, "n": 56}), "69.6")


class TestFillN(unittest.TestCase):
    def test_older_results_get_n_from_document_counts(self):
        p = {"adm_real.termin": {"accuracy": 0.714}, "sad_real.rodzaj": {"accuracy": 0.989, "n": 89}}
        out = fill_n(p, {"adm_real": 56, "sad_real": 90})
        self.assertEqual(out["adm_real.termin"]["n"], 56)
        self.assertEqual(out["sad_real.rodzaj"]["n"], 89)  # stored n wins
        self.assertNotIn("n", p["adm_real.termin"])        # input not modified

    def test_unknown_domain_stays_without_n(self):
        self.assertNotIn("n", fill_n({"x.q": {"accuracy": 0.5}}, {})["x.q"])


class TestModelIndex(unittest.TestCase):
    def test_yaml_with_both_results(self):
        y = model_index(0.8642, 0.8657)
        self.assertTrue(y.startswith("model-index:\n- name: jerzyk-1.0\n"))
        self.assertIn("type: trenify/jerzyk-bench", y)
        self.assertIn("value: 86.4\n", y)
        self.assertIn("value: 86.6\n", y)
        self.assertEqual(y.count("- task:"), 2)


class TestNormaliseFile(unittest.TestCase):
    OLD = {
        "wynik": {
            "model": "jerzyk-v4-kal", "n_pism": 480, "trafnosc_srednia_dziedzin": 0.864, "ece": 0.052,
            "ms_mediana": 128, "ms_p95": 171,
            "pytania": {"adm.pilnosc": {"trafnosc": 0.775, "trafnosc_pm1": 0.825, "mae": 0.61},
                        "adm.termin": {"trafnosc": 0.825, "brier": 0.141}},
        },
        "szczegoly": [{"id": "adm-test-000", "q": "adm.termin", "gold": "tak", "pred": "tak", "conf": 0.9}],
    }
    NEW = {
        "result": {
            "model": "jerzyk-v4-kal", "n_documents": 480, "mean_accuracy_over_domains": 0.864, "ece": 0.052,
            "ms_median": 128, "ms_p95": 171,
            "questions": {"adm.pilnosc": {"accuracy": 0.775, "accuracy_pm1": 0.825, "mae": 0.61},
                          "adm.termin": {"accuracy": 0.825, "brier": 0.141}},
        },
        "details": [{"id": "adm-test-000", "q": "adm.termin", "gold": "tak", "pred": "tak", "conf": 0.9}],
    }

    def test_old_polish_schema_reads_as_new(self):
        self.assertEqual(normalise_file(self.OLD), self.NEW)

    def test_new_schema_is_unchanged(self):
        self.assertEqual(normalise_file(self.NEW), self.NEW)

    def test_input_not_modified(self):
        before = json.dumps(self.OLD, sort_keys=True)
        normalise_file(self.OLD)
        self.assertEqual(json.dumps(self.OLD, sort_keys=True), before)


class TestDocumentCounts(unittest.TestCase):
    def test_counts_domain_and_skips_rows_marked_not_ok(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder / "sad_test.jsonl").write_text(
                '{"id": "a", "domain": "sad"}\n{"id": "b", "domain": "sad", "ok": false}\n\n', encoding="utf-8")
            (folder / "adm_real_test.jsonl").write_text('{"id": "c", "domain": "adm_real", "ok": true}\n', encoding="utf-8")
            (folder / "dev.jsonl").write_text('{"id": "d", "domain": "adm"}\n', encoding="utf-8")  # not a *_test file
            self.assertEqual(document_counts(folder), {"sad": 1, "adm_real": 1})


class TestReadHardware(unittest.TestCase):
    def test_new_file_wins_and_old_is_fallback(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(results_table, "RESULTS", Path(d)):
            self.assertIsNone(read_hardware())
            (Path(d) / "sprzet-pub.txt").write_text("Old Mac\n", encoding="utf-8")
            self.assertEqual(read_hardware(), "Old Mac")
            (Path(d) / "hardware-published.txt").write_text("NVIDIA GPU\n", encoding="utf-8")
            self.assertEqual(read_hardware(), "NVIDIA GPU")


class TestTableNames(unittest.TestCase):
    def test_rows_use_english_question_names(self):
        import contextlib
        import io
        from scripts.results_table import print_table
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print_table({"M": {"adm_real.pilnosc": {"accuracy": 0.5, "n": 10}}}, "T")
        self.assertIn("Admin. notices (real): urgency", buf.getvalue())
        self.assertNotIn("pilnosc", buf.getvalue())

    def test_model_without_results_gets_dashes(self):
        import contextlib
        import io
        from scripts.results_table import print_table
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print_table({"A": {"sad.rodzaj": {"accuracy": 0.5}}, "B": {}}, "T")
        self.assertIn("| Court: document_type | 50.0 | – |", buf.getvalue())
        self.assertIn("| **Mean over domains** | **50.0** | – |", buf.getvalue())


class LatencyCellTest(unittest.TestCase):
    def test_same_machine(self):
        self.assertEqual(latency_cell("Qwen3 8B", 240, {}), "0.24 s")

    def test_other_machine_is_labelled(self):
        self.assertEqual(latency_cell("basal", 1130, {"basal": "Apple M1, MLX"}), "1.13 s (Apple M1, MLX)")


if __name__ == "__main__":
    unittest.main()
