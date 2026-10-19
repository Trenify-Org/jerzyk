"""Tests for deadlines.py: Polish calendar rules and deadline extraction.

  python -m unittest tests.test_deadlines
"""
import unittest
from datetime import date

from jerzyk.deadlines import deadline_end, easter, find, nearest, next_working_day


class Calendar(unittest.TestCase):
    def test_easter(self):
        self.assertEqual(easter(2026), date(2026, 4, 5))
        self.assertEqual(easter(2027), date(2027, 3, 28))

    def test_saturday_and_holiday_move_the_end(self):
        self.assertEqual(next_working_day(date(2026, 11, 14)), date(2026, 11, 16))  # Saturday
        self.assertEqual(next_working_day(date(2026, 11, 11)), date(2026, 11, 12))  # Independence Day
        self.assertEqual(next_working_day(date(2026, 12, 24)), date(2026, 12, 28))  # Christmas Eve, Christmas, weekend

    def test_month_ends_on_last_day(self):
        self.assertEqual(deadline_end(date(2027, 1, 29), 1, "miesiąca"), date(2027, 3, 1))  # 28.02 is a Sunday
        self.assertEqual(deadline_end(date(2026, 1, 31), 1, "miesiąca"), date(2026, 3, 2))  # 28.02 is a Saturday
        self.assertEqual(deadline_end(date(2025, 1, 31), 1, "miesiąca"), date(2025, 2, 28))  # Friday


class Extraction(unittest.TestCase):
    def test_days_from_delivery(self):
        t = find("Wzywa się do uzupełnienia braków w terminie 7 dni od doręczenia wezwania.", date(2026, 11, 6))
        self.assertEqual(len(t), 1)
        self.assertEqual(t[0].date, date(2026, 11, 13))
        self.assertEqual(t[0].kind, "from_delivery")

    def test_numerals_and_weeks(self):
        t = find("Zażalenie wnosi się w terminie tygodnia od dnia doręczenia postanowienia.", date(2026, 11, 2))
        self.assertEqual(t[0].date, date(2026, 11, 9))
        t = find("w terminie dwóch tygodni od doręczenia nakazu", date(2026, 11, 2))
        self.assertEqual(t[0].date, date(2026, 11, 16))
        t = find("w terminie czternastu dni od daty doręczenia", date(2026, 10, 28))
        self.assertEqual(t[0].date, date(2026, 11, 12))  # the 11.11 holiday does not matter, ends 12.11 (Thursday)

    def test_end_on_holiday(self):
        t = find("w terminie 14 dni od doręczenia", date(2026, 10, 28))
        self.assertEqual(t[0].date, date(2026, 11, 12))
        t = find("w terminie 7 dni od doręczenia", date(2026, 11, 4))
        self.assertEqual(t[0].date, date(2026, 11, 12))  # 11.11 → 12.11

    def test_no_delivery_date(self):
        t = find("w terminie 7 dni od doręczenia")
        self.assertIsNone(t[0].date)

    def test_explicit_dates(self):
        t = find("Rozprawa odbędzie się w dniu 18 listopada 2026 r. o godz. 10:30.")
        self.assertEqual([x.date for x in t], [date(2026, 11, 18)])
        t = find("Proszę o przesłanie poprawek do 20.11.2026.")
        self.assertEqual([x.date for x in t], [date(2026, 11, 20)])

    def test_letter_date_is_not_a_deadline(self):
        self.assertEqual(find("Warszawa, 3 listopada 2026 r. Umowa z 5 stycznia 2026 r."), [])

    def test_immediately(self):
        t = find("Prosimy o niezwłoczne... niezwłocznie uregulować", date(2026, 11, 3))
        self.assertEqual(t[-1].kind, "immediately")

    def test_nearest(self):
        tekst = ("Sąd wyznacza rozprawę na dzień 2 grudnia 2026 r. i zobowiązuje pełnomocnika "
                 "do złożenia pisma w terminie 7 dni od doręczenia.")
        self.assertEqual(nearest(tekst, date(2026, 11, 2)).date, date(2026, 11, 9))

    def test_header_date_is_not_a_deadline(self):
        self.assertEqual(find("Wójt Gminy Nowa Wieś, dnia 12 października 2026 r. Decyzja z dnia 3 marca 2026 r."), [])

    def test_from_publication(self):
        t = find("Strony mogą wnieść uwagi w terminie 7 dni od dnia publikacji obwieszczenia.", date(2026, 10, 12))
        self.assertEqual(t[0].date, date(2026, 10, 19))


if __name__ == "__main__":
    unittest.main()
