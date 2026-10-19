"""Tests for jerzyk/labels.py: English names of the Polish questions and answers the model was trained on.

  python -m unittest tests.test_labels
"""
import unittest

from jerzyk.labels import ANSWER_NAMES, QUESTION_NAMES, to_english
from jerzyk.questions import questions

DOMAINS = ("sad", "adm", "ksieg", "email")


class TestCoverage(unittest.TestCase):
    def test_every_question_has_an_english_name(self):
        for domain in DOMAINS:
            for qid in questions(domain):
                self.assertIn(qid, QUESTION_NAMES, (domain, qid))

    def test_every_choice_option_has_an_english_name(self):
        for domain in DOMAINS:
            for qid, q in questions(domain).items():
                if q["type"] == "choice":
                    self.assertEqual(set(ANSWER_NAMES[(domain, qid)]), set(q["criteria"]), (domain, qid))

    def test_names_are_unique_within_a_question(self):
        self.assertEqual(len(set(QUESTION_NAMES.values())), len(QUESTION_NAMES))
        for key, names in ANSWER_NAMES.items():
            self.assertEqual(len(set(names.values())), len(names), key)

    def test_names_are_identifiers(self):
        for name in [*QUESTION_NAMES.values(), *(n for names in ANSWER_NAMES.values() for n in names.values())]:
            self.assertRegex(name, r"^[a-z][a-z_]*$")


class TestToEnglish(unittest.TestCase):
    def test_translates_questions_and_choices(self):
        out = to_english({"rodzaj": ("wezwanie_sadu", 0.99), "termin": (True, 0.9), "pilnosc": (3, 0.8)}, "sad")
        self.assertEqual(out, {"document_type": ("court_summons", 0.99), "deadline": (True, 0.9), "urgency": (3, 0.8)})

    def test_same_polish_option_differs_by_domain(self):
        court = to_english({"rodzaj": ("postanowienie", 0.9)}, "sad")
        admin = to_english({"rodzaj": ("postanowienie", 0.9)}, "adm")
        self.assertNotEqual(court["document_type"][0], admin["document_type"][0])

    def test_own_questions_pass_through(self):
        self.assertEqual(to_english({"moje_pytanie": ("tak", 0.7)}, "sad"), {"moje_pytanie": ("tak", 0.7)})

    def test_input_not_modified(self):
        answers = {"dzial": ("sprzedaz", 0.9)}
        to_english(answers, "email")
        self.assertEqual(answers, {"dzial": ("sprzedaz", 0.9)})


if __name__ == "__main__":
    unittest.main()
