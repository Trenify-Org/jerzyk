"""Tests for scripts/anonymize_rulings.py: names of judges, prosecutors and clerks in real court rulings.

  python -m unittest tests.test_anonymize_rulings
"""
import unittest

from scripts.anonymize_rulings import MANUAL_FIXES, anonymize, apply_manual_fixes


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


class TestManualFixes(unittest.TestCase):
    """Leaks found by the read-through of 2026-10-19 that the rules do not catch."""

    def test_fix_is_applied_to_its_document_only(self):
        row = {"id": "sad_real_dev-027", "state": "Protokolant [PROTOKOLANT] Fabiszewska \n przy udziale"}
        other = {"id": "sad_real_dev-028", "state": row["state"]}
        self.assertEqual(apply_manual_fixes(row)["state"], "Protokolant [PROTOKOLANT] \n przy udziale")
        self.assertEqual(apply_manual_fixes(other)["state"], other["state"])

    def test_input_row_is_not_modified(self):
        row = {"id": "sad_real-000", "state": "z udziałem H. I. (Szok), Ł. A."}
        self.assertEqual(apply_manual_fixes(row)["state"], "z udziałem H. I., Ł. A.")
        self.assertEqual(row["state"], "z udziałem H. I. (Szok), Ł. A.")

    def test_applying_twice_changes_nothing(self):
        row = {"id": "sad_real_dev-047", "state": "K. Ł. , T. A. oraz Amina A. A. pozwem"}
        once = apply_manual_fixes(row)
        self.assertEqual(apply_manual_fixes(once), once)

    def test_every_fix_removes_or_masks_text(self):
        for fixes in MANUAL_FIXES.values():
            for old, new in fixes:
                self.assertTrue(len(new) < len(old) or "[" in new, (old, new))


if __name__ == "__main__":
    unittest.main()
