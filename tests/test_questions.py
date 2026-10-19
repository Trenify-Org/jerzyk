"""The question texts are model input: Jerzyk 1.0 was trained on exactly these strings.

  python -m unittest tests.test_questions
"""
import json
import unittest
from pathlib import Path

from jerzyk.questions import RECIPES, questions

FIXTURES = Path(__file__).parent / "fixtures"


class TestQuestionsUnchanged(unittest.TestCase):
    def test_questions_match_jerzyk_1_0(self):
        expected = json.loads((FIXTURES / "questions-1.0.json").read_text(encoding="utf-8"))
        for domain, qs in expected.items():
            self.assertEqual(questions(domain), qs, domain)

    def test_recipes_match_jerzyk_1_0(self):
        expected = json.loads((FIXTURES / "recipes-1.0.json").read_text(encoding="utf-8"))
        self.assertEqual({d: [list(r) for r in v] for d, v in RECIPES.items()}, expected)


class TestQuestionsAreCopies(unittest.TestCase):
    def test_changing_the_result_does_not_affect_later_calls(self):
        q = questions("email")
        q["pilnosc"]["criteria"].append("x")
        q["dzial"]["criteria"]["nowy"] = "x"
        self.assertNotIn("x", questions("email")["pilnosc"]["criteria"])
        self.assertNotIn("nowy", questions("email")["dzial"]["criteria"])


if __name__ == "__main__":
    unittest.main()
