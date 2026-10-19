"""deadlines — finds and computes deadlines in Polish official letters (rule-based, no model).

    >>> from datetime import date
    >>> from jerzyk.deadlines import find
    >>> find("Wzywa się do uzupełnienia braków w terminie 7 dni od doręczenia.", delivery=date(2026, 11, 6))
    [Deadline(date=datetime.date(2026, 11, 13), kind='from_delivery', fragment='w terminie 7 dni od doręczenia')]

Counting rules (art. 111–115 of the Civil Code, art. 165 § 1 KPC, art. 57 KPA):
- in days: the day of delivery is not counted, the deadline ends at the end of the last day,
- in weeks / months: it ends on the day matching the delivery day by name or date
  (if the month has no such day, on the last day of the month),
- an end on a Saturday or a public holiday moves to the next working day (Christmas Eve is a holiday from 2025).
Explicit dates in the letter ("do dnia 15 listopada 2026 r.", "rozprawa 18.11.2026") are returned unchanged.

Main functions: find (all deadlines in a letter), nearest (the nearest one), deadline_end, next_working_day.
The patterns match Polish text, so the regular expressions and word lists below stay in Polish.
"""
import calendar
import re
from dataclasses import dataclass
from datetime import date as Date, timedelta
from typing import FrozenSet, List, Optional

MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6, "lipca": 7,
    "sierpnia": 8, "września": 9, "października": 10, "listopada": 11, "grudnia": 12,
}
NUMERALS = {
    "jednego": 1, "dwóch": 2, "dwu": 2, "trzech": 3, "czterech": 4, "pięciu": 5, "sześciu": 6,
    "siedmiu": 7, "ośmiu": 8, "dziewięciu": 9, "dziesięciu": 10, "czternastu": 14, "dwudziestu": 20,
    "dwudziestu jeden": 21, "trzydziestu": 30, "sześćdziesięciu": 60,
}
_NUMBER = r"(\d{1,3}|" + "|".join(sorted(NUMERALS, key=len, reverse=True)) + r")"
_FROM = (r"(?:od\s+(?:dnia\s+|daty\s+)?(?:doręczenia|otrzymania|odebrania|daty\s+doręczenia|publikacji|ogłoszenia|"
       r"publicznego\s+ogłoszenia|wywieszenia|udostępnienia|zawiadomienia)[\w\s]{0,40}?)")


@dataclass(frozen=True)
class Deadline:
    date: Optional[Date]   # None for a relative deadline when no delivery date is given
    kind: str              # 'from_delivery' | 'date' (explicit date in the letter) | 'immediately'
    fragment: str          # matched text


def easter(year: int) -> Date:
    """Easter Sunday (Gregorian calendar, anonymous algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    return Date(year, month, (h + l - 7 * m + 114) % 31 + 1)


def holidays(year: int) -> FrozenSet[Date]:
    """Polish public holidays (non-working days) in a year."""
    e = easter(year)
    days = {Date(year, 1, 1), Date(year, 1, 6), e, e + timedelta(days=1), Date(year, 5, 1), Date(year, 5, 3),
            e + timedelta(days=49), e + timedelta(days=60), Date(year, 8, 15), Date(year, 11, 1),
            Date(year, 11, 11), Date(year, 12, 25), Date(year, 12, 26)}
    if year >= 2025:
        days.add(Date(year, 12, 24))  # Christmas Eve is a public holiday from 2025
    return frozenset(days)


def next_working_day(d: Date) -> Date:
    """Moves a deadline ending on a Saturday, Sunday or public holiday to the next working day."""
    while d.weekday() >= 5 or d in holidays(d.year):
        d += timedelta(days=1)
    return d


def add_months(d: Date, n: int) -> Date:
    """Same day n months later, or the last day of that month if it is shorter."""
    m = d.month - 1 + n
    year, month = d.year + m // 12, m % 12 + 1
    return Date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def deadline_end(start: Date, count: int, unit: str) -> Date:
    """End of a deadline of `count` units from `start`; `unit` is a Polish word (dni, tygodni, miesięcy…)."""
    if unit.startswith("dni") or unit.startswith("dzie"):
        end = start + timedelta(days=count)
    elif unit.startswith("tydz") or unit.startswith("tygod"):
        end = start + timedelta(weeks=count)
    else:
        end = add_months(start, count)
    return next_working_day(end)


def _number(s: str) -> int:
    s = s.strip().lower()
    return int(s) if s.isdigit() else NUMERALS[s]


def _parse_date(day: str, month: str, year: str) -> Optional[Date]:
    try:
        m = MONTHS.get(month.lower()) or int(month)
        return Date(int(year), m, int(day))
    except (ValueError, TypeError):
        return None


_PATTERNS = [
    # matches e.g. „w terminie 7 dni od doręczenia”, „w terminie czternastu dni od dnia otrzymania”
    ("from_delivery", re.compile(r"w\s+(?:nieprzekraczalnym\s+)?terminie\s+" + _NUMBER + r"\s+(dni|tygodni|miesięcy)\s+" + _FROM, re.I)),
    # matches e.g. „w terminie tygodnia / dwóch tygodni / miesiąca od doręczenia”
    ("from_delivery", re.compile(r"w\s+(?:nieprzekraczalnym\s+)?terminie\s+(?:(" + "|".join(NUMERALS) + r")\s+)?(tygodnia|tygodni|miesiąca|miesięcy)\s+" + _FROM, re.I)),
    # matches e.g. „w ciągu 14 dni od doręczenia”
    ("from_delivery", re.compile(r"w\s+ciągu\s+" + _NUMBER + r"\s+(dni|tygodni|miesięcy)\s+" + _FROM, re.I)),
]
_DATE_WORDS = re.compile(r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(\d{4})", re.I)
_DATE_DIGITS = re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})\b")
_DATE_CONTEXT = re.compile(r"(do\s+dnia|do|na\s+dzień|w\s+dniu|dnia|odbędzie\s+się|wyznacz\w*\s+na)\s*$", re.I)
_LETTER_DATE = re.compile(r"(,|\bz)\s*dnia\s*$", re.I)
_IMMEDIATELY = re.compile(r"\bniezwłocznie\b", re.I)


def find(text: str, delivery: Optional[Date] = None) -> List[Deadline]:
    """All deadlines in a letter. Relative ones are counted from `delivery` (delivery date; None → date=None)."""
    found = []
    taken = []
    for kind, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            if any(a <= m.start() < b for a, b in taken):
                continue
            taken.append(m.span())
            count_s, unit = m.group(1), m.group(2).lower()
            count = _number(count_s) if count_s else 1
            end = deadline_end(delivery, count, unit) if delivery else None
            found.append(Deadline(end, kind, m.group(0).strip()))

    for pattern, parse in ((_DATE_WORDS, lambda m: _parse_date(*m.groups())),
                           (_DATE_DIGITS, lambda m: _parse_date(m.group(1), m.group(2), m.group(3)))):
        for m in pattern.finditer(text):
            before = text[max(0, m.start() - 25):m.start()]
            if not _DATE_CONTEXT.search(before) or _LETTER_DATE.search(before):
                continue  # date of the letter ("Warszawa, dnia …", "pismo z dnia …"), of a contract etc. — not a deadline
            d = parse(m)
            if d:
                found.append(Deadline(d, "date", text[max(0, m.start() - 12):m.end()].strip()))

    if _IMMEDIATELY.search(text):
        found.append(Deadline(delivery, "immediately", "niezwłocznie"))
    return found


def nearest(text: str, delivery: Optional[Date] = None, today: Optional[Date] = None) -> Optional[Deadline]:
    """The nearest deadline not earlier than `today` (defaults to the delivery date)."""
    since = today or delivery
    candidates = [d for d in find(text, delivery) if d.date and (since is None or d.date >= since)]
    return min(candidates, key=lambda d: d.date, default=None)
