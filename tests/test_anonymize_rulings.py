"""Tests for scripts/anonymize_rulings.py: names of judges, prosecutors and clerks in real court rulings.

  python -m unittest tests.test_anonymize_rulings
"""
import unittest

from scripts.anonymize_rulings import anonymize


class TestInflections(unittest.TestCase):
    """Cases from the pre-publication review: surnames in the genitive got past the rules."""

    def test_judge_in_genitive(self):
        t = anonymize("Zarządzeniem sędziego Urszuli Iwanowskiej wyznaczono termin.")
        self.assertNotIn("Iwanowsk", t)
        self.assertNotIn("Urszul", t)

    def test_prosecutor_after_city_name(self):
        t = anonymize("przy udziale Prokuratora Prokuratury Rejonowej w Poznaniu Zdzisława Kowalskiego")
        self.assertNotIn("Kowalsk", t)
        self.assertNotIn("Zdzisław", t)
        t = anonymize("przy udziale Prokuratora Prokuratury Rejonowej w Poznaniu Mateusza Nowaka")
        self.assertNotIn("Nowak", t)

    def test_female_first_name_in_genitive(self):
        self.assertNotIn("Malinowsk", anonymize("z udziałem Marii Malinowskiej"))
        self.assertNotIn("Zielińsk", anonymize("wobec Anny Zielińskiej"))


class TestMetadata(unittest.TestCase):
    def test_judge_from_metadata_also_inflected(self):
        t = anonymize("Przewodniczący: SSR Robert Troll. Sędzia Trolla nie było.", judges=["Robert Troll"])
        self.assertNotIn("Troll", t)
        self.assertIn("[SĘDZIA]", t)

    def test_clerk(self):
        t = anonymize("Protokolant: Anna Kot", clerks=["Anna Kot"])
        self.assertNotIn("Kot", t)


class TestNoLossOfContent(unittest.TestCase):
    def test_institution_names_stay(self):
        t = anonymize("Sąd Rejonowy w Poznaniu, Wydział I Cywilny, oddalił powództwo.")
        self.assertEqual(t, "Sąd Rejonowy w Poznaniu, Wydział I Cywilny, oddalił powództwo.")

    def test_party_initials_stay(self):
        self.assertIn("L. E.", anonymize("powód L. E. wniósł apelację"))


if __name__ == "__main__":
    unittest.main()
