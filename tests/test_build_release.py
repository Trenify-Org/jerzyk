"""Tests for scripts/build_release.py (release build), run in temporary folders.

  python3 -m unittest discover -s tests -t .
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_release import (
    TEST_FILES, build_model, clean_folder, clean_row, copy_code, copy_templates, fill_markers, write_dataset,
)


def _write(path, text=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class TestCleanFolder(unittest.TestCase):
    def test_keeps_git_and_removes_the_rest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
            (root / ".gitignore").write_text("x\n")
            (root / "old.py").write_text("")
            (root / "demo").mkdir()
            (root / "demo" / "index.html").write_text("")
            clean_folder(root)
            self.assertEqual([p.name for p in root.iterdir()], [".git"])
            self.assertTrue((root / ".git" / "HEAD").exists())

    def test_missing_folder_is_fine(self):
        with tempfile.TemporaryDirectory() as d:
            clean_folder(Path(d) / "nope")


class TestCleanRow(unittest.TestCase):
    def test_keeps_only_published_fields_in_order(self):
        row = {"note": "n", "zzz": 1, "state": "s", "id": "i", "domain": "sad", "split": "test",
               "questions": {}, "expected": {}, "source": "x", "author": "a", "labels": {}}
        self.assertEqual(list(clean_row(row)), ["id", "domain", "split", "state", "questions", "expected",
                                                "source", "author", "labels", "note"])

    def test_real_rows_are_not_masked(self):
        row = {"id": "i", "state": "PESEL 12345678901, mail jan@firma.pl"}
        self.assertEqual(clean_row(row, generated=False)["state"], row["state"])

    def test_generated_rows_are_masked(self):
        row = {"id": "i", "state": "PESEL 12345678901, tel. 601 234 567, jan.kowal@firma.com.pl"}
        self.assertEqual(clean_row(row, generated=True)["state"],
                         "PESEL [PESEL], tel. [TELEFON], jan.kowal@example.pl")

    def test_input_not_modified(self):
        row = {"id": "i", "state": "PESEL 12345678901"}
        clean_row(row, generated=True)
        self.assertEqual(row["state"], "PESEL 12345678901")


class TestCopyCode(unittest.TestCase):
    def test_copies_code_without_cache_archive_or_root_files(self):
        with tempfile.TemporaryDirectory() as d:
            root, github = Path(d) / "repo", Path(d) / "github"
            _write(root / "jerzyk" / "model.py", "x")
            _write(root / "jerzyk" / "__pycache__" / "model.cpython.pyc", "x")
            _write(root / "jerzyk" / "demo" / "index.html", "<html>")
            _write(root / "scripts" / "__init__.py", "")
            _write(root / "scripts" / "train.sh", "#!/bin/sh")
            _write(root / "scripts" / "notes.txt", "not code")
            _write(root / "scripts" / "sub" / "deep.py", "not copied")
            _write(root / "tests" / "test_model.py", "")
            _write(root / "tests" / "fixtures" / "sample.jsonl", "")
            _write(root / "docs" / "SPEC.md", "")
            _write(root / "docs" / "TRAINING.md", "")
            _write(root / "docs" / "OTHER.md", "")
            _write(root / "pyproject.toml", "[project]")
            _write(root / "archive" / "old.py", "")
            _write(root / "HANDOFF.md", "")
            _write(root / "pakuj.sh", "")
            github.mkdir()
            copy_code(root, github)
            self.assertTrue((github / "jerzyk" / "model.py").exists())
            self.assertTrue((github / "jerzyk" / "demo" / "index.html").exists())
            self.assertFalse((github / "jerzyk" / "__pycache__").exists())
            self.assertEqual(sorted(p.name for p in (github / "scripts").iterdir()),
                             ["__init__.py", "train.sh"])
            self.assertTrue((github / "tests" / "fixtures" / "sample.jsonl").exists())
            self.assertEqual(sorted(p.name for p in (github / "docs").iterdir()), ["SPEC.md", "TRAINING.md"])
            self.assertTrue((github / "pyproject.toml").exists())
            for absent in ("archive", "HANDOFF.md", "pakuj.sh"):
                self.assertFalse((github / absent).exists())


class TestCopyTemplates(unittest.TestCase):
    def test_copies_github_templates_and_dot_github(self):
        with tempfile.TemporaryDirectory() as d:
            templates, github = Path(d) / "szablony", Path(d) / "github"
            for f in ("github-README.md", "github-NOTICE", "github-.gitignore", "github-requirements.txt"):
                _write(templates / f, f)
            _write(templates / "github-.github" / "workflows" / "ci.yml", "on: push")
            github.mkdir()
            copy_templates(templates, github)
            self.assertEqual((github / "README.md").read_text(), "github-README.md")
            self.assertEqual((github / ".gitignore").read_text(), "github-.gitignore")
            self.assertFalse((github / "CITATION.cff").exists())  # template missing: skipped
            self.assertTrue((github / ".github" / "workflows" / "ci.yml").exists())


class TestBuildModel(unittest.TestCase):
    def test_copies_weights_without_checkpoints_and_adds_card(self):
        with tempfile.TemporaryDirectory() as d:
            weights, templates, model = Path(d) / "w", Path(d) / "t", Path(d) / "hf-model"
            _write(weights / "model.safetensors", "w")
            _write(weights / "checkpoint_latest" / "x.bin", "c")
            _write(templates / "hf-model-README.md", "card")
            _write(templates / "github-NOTICE", "notice")
            build_model(weights, model, templates)
            self.assertTrue((model / "model.safetensors").exists())
            self.assertFalse((model / "checkpoint_latest").exists())
            self.assertEqual((model / "README.md").read_text(), "card")
            self.assertEqual((model / "NOTICE").read_text(), "notice")


def _row(name):
    return {"id": f"{name}-000", "domain": name.split("_test")[0].split("_dev")[0], "split": "test",
            "state": "PESEL 12345678901", "questions": {}, "expected": {}, "source": "s", "note": "n"}


class TestWriteDataset(unittest.TestCase):
    def test_writes_masked_generated_and_real_rows(self):
        with tempfile.TemporaryDirectory() as d:
            bench, anonymised, out = Path(d) / "bench", Path(d) / "anon", Path(d) / "out"
            for name in TEST_FILES:
                src = anonymised if name.startswith(("adm_real", "sad_real")) else bench
                _write(src / f"{name}.jsonl", json.dumps(_row(name)) + "\n\n")
            with contextlib.redirect_stdout(io.StringIO()):
                write_dataset(bench, anonymised, out)
            self.assertEqual(sorted(p.name for p in out.iterdir()), sorted(f"{n}.jsonl" for n in TEST_FILES))
            generated = json.loads((out / "sad_test.jsonl").read_text())
            real = json.loads((out / "sad_real_test.jsonl").read_text())
            self.assertEqual(generated["state"], "PESEL [PESEL]")
            self.assertEqual(real["state"], "PESEL 12345678901")

    def test_missing_anonymised_real_file_stops_the_build(self):
        with tempfile.TemporaryDirectory() as d:
            bench, anonymised = Path(d) / "bench", Path(d) / "anon"
            _write(bench / "sad_test.jsonl", json.dumps(_row("sad_test")) + "\n")
            with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()):
                write_dataset(bench, anonymised, Path(d) / "out")


class TestFillMarkers(unittest.TestCase):
    def test_inserts_tables_and_note_and_collapses_blank_lines(self):
        text = "a\n\n<!-- RESULTS -->\n\n\n<!-- ANONYMIZATION_NOTE -->\nz"
        out = fill_markers(text, "| table |\n", "> note")
        self.assertEqual(out, "a\n\n| table |\n\n> note\nz")

    def test_empty_note_removes_marker(self):
        self.assertEqual(fill_markers("<!-- ANONYMIZATION_NOTE -->", "", ""), "")


if __name__ == "__main__":
    unittest.main()
