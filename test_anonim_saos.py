"""Tests for anonim_saos.py: names of judges, prosecutors and clerks in real court rulings.

  python3 -m unittest test_anonim_saos
"""
import unittest

from anonim_saos import anonimizuj


class TestOdmiana(unittest.TestCase):
    """Przypadki z przeglądu przed publikacją: nazwiska w dopełniaczu przechodziły przez reguły."""

    def test_sedziego_w_dopelniaczu(self):
        t = anonimizuj("Zarządzeniem sędziego Urszuli Iwanowskiej wyznaczono termin.")
        self.assertNotIn("Iwanowsk", t)
        self.assertNotIn("Urszul", t)

    def test_prokurator_po_nazwie_miasta(self):
        t = anonimizuj("przy udziale Prokuratora Prokuratury Rejonowej w Poznaniu Zdzisława Kowalskiego")
        self.assertNotIn("Kowalsk", t)
        self.assertNotIn("Zdzisław", t)
        t = anonimizuj("przy udziale Prokuratora Prokuratury Rejonowej w Poznaniu Mateusza Nowaka")
        self.assertNotIn("Nowak", t)

    def test_imie_zenskie_w_dopelniaczu(self):
        self.assertNotIn("Malinowsk", anonimizuj("z udziałem Marii Malinowskiej"))
        self.assertNotIn("Zielińsk", anonimizuj("wobec Anny Zielińskiej"))


class TestMetadane(unittest.TestCase):
    def test_sedzia_z_metadanych_takze_w_odmianie(self):
        t = anonimizuj("Przewodniczący: SSR Robert Troll. Sędzia Trolla nie było.", sedziowie=["Robert Troll"])
        self.assertNotIn("Troll", t)
        self.assertIn("[SĘDZIA]", t)

    def test_protokolant(self):
        t = anonimizuj("Protokolant: Anna Kot", protokolanci=["Anna Kot"])
        self.assertNotIn("Kot", t)


class TestBezStratTresci(unittest.TestCase):
    def test_nazwy_instytucji_zostaja(self):
        t = anonimizuj("Sąd Rejonowy w Poznaniu, Wydział I Cywilny, oddalił powództwo.")
        self.assertEqual(t, "Sąd Rejonowy w Poznaniu, Wydział I Cywilny, oddalił powództwo.")

    def test_inicjaly_stron_zostaja(self):
        self.assertIn("L. E.", anonimizuj("powód L. E. wniósł apelację"))


if __name__ == "__main__":
    unittest.main()
