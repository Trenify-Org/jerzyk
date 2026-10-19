"""Tests for wydanie.py (release build).

  python3 -m unittest test_wydanie
"""
import tempfile
import unittest
from pathlib import Path

from wydanie import wyczysc


class TestWyczysc(unittest.TestCase):
    def test_keeps_git_and_removes_the_rest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
            (root / ".gitignore").write_text("x\n")
            (root / "old.py").write_text("")
            (root / "demo").mkdir()
            (root / "demo" / "index.html").write_text("")
            wyczysc(root)
            self.assertEqual([p.name for p in root.iterdir()], [".git"])
            self.assertTrue((root / ".git" / "HEAD").exists())

    def test_missing_folder_is_fine(self):
        with tempfile.TemporaryDirectory() as d:
            wyczysc(Path(d) / "nope")


if __name__ == "__main__":
    unittest.main()
