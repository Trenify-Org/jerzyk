"""Generates the test and dev sets of jerzyk-bench with answers taken from the recipes (jerzyk.questions.RECIPES).

  python -m scripts.generate_benchmark --url http://127.0.0.1:9934   # data/bench/{domain}_{split}.jsonl
"""
import argparse
import datetime as dt
import json
import random
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from jerzyk.questions import COST_CATEGORIES, COST_DOCUMENT_TYPES, DOCUMENT_TYPES, RECIPES, URGENCY_EMAIL, questions
from scripts.llm import post

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "bench"
SPLITS = {"test": 120, "dev": 30}
MONTHS_PL = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
             "września", "października", "listopada", "grudnia"]
RECIPIENT = {
    "sad": "kancelarii prawnej (pełnomocnika strony)",
    "adm": "pracowni architektonicznej (projektanta lub pełnomocnika inwestora)",
    "ksieg": "biura rachunkowego (w imieniu klienta)",
}


FIRST_NAMES = ["Anna", "Piotr", "Katarzyna", "Tomasz", "Magdalena", "Marcin", "Agnieszka", "Paweł", "Joanna", "Krzysztof",
               "Ewa", "Michał", "Barbara", "Grzegorz", "Natalia", "Łukasz", "Monika", "Jakub", "Aleksandra", "Wojciech"]
SURNAMES = ["Wiśniewski", "Wójcik", "Kamiński", "Lewandowski", "Zieliński", "Szymański", "Woźniak", "Dąbrowski",
            "Kozłowski", "Jankowski", "Mazur", "Krawczyk", "Piotrowski", "Grabowski", "Pawlak", "Michalski",
            "Zając", "Król", "Wieczorek", "Jabłoński", "Majewski", "Olszewski", "Stępień", "Malinowski", "Górski"]
COMPANIES = ["Budrex", "Termo-Plan", "Agro-Vit", "Mostostal-Pom", "Nordis", "Kwadrat Studio", "Elmax", "Delta-Inwest",
             "Wodex", "Polbet", "Alfa-Med", "Trans-Kar", "Glob-Tech", "Sokół Development", "Ekoterm", "Retail-Point"]
CITIES = ["Warszawa", "Kraków", "Gdańsk", "Wrocław", "Poznań", "Łódź", "Lublin", "Białystok", "Rzeszów", "Olsztyn",
          "Kielce", "Opole", "Toruń", "Szczecin", "Zielona Góra", "Katowice", "Bydgoszcz", "Koszalin", "Płock", "Nowy Sącz"]
COMPANY_FORMS = ["sp. z o.o.", "S.A.", "sp.j.", "sp.k."]


def date_pl(d):
    """Date written the Polish way, e.g. '5 stycznia 2026 r.'."""
    return f"{d.day} {MONTHS_PL[d.month - 1]} {d.year} r."


def person(rng):
    surname = rng.choice(SURNAMES)
    first = rng.choice(FIRST_NAMES)
    if first.endswith("a") and surname.endswith("ski"):
        surname = surname[:-1] + "a"
    return f"{first} {surname}"


PRODUCTS = ["ekspres do kawy", "rower elektryczny", "pakiet internetu światłowodowego", "kurtka zimowa", "laptop",
            "abonament na oprogramowanie", "zestaw mebli ogrodowych", "karnet na siłownię", "smartfon", "odkurzacz",
            "kurs online", "opony zimowe", "konto firmowe", "hosting strony", "zestaw kosmetyków"]


# Scenarios consistent with the department: drawing the department and an unrelated product gave contradictory e-mails.
# Scenario → allowed urgency levels (SPEC.md, e-mail scale). v1 drew urgency independently of the scenario,
# which gave contradictory pairs ("asks about work" + critical) and label noise — hence 44–54% for all models.
EMAIL_SCENARIOS = {
    "sprzedaz": [("pyta o cenę, dostępność albo rabat na produkt przed zakupem", (0,)),
                 ("prosi o ofertę dla firmy na kilka sztuk", (0, 1)), ("pyta, czym różnią się dwa warianty produktu", (0,))],
    "zamowienia_i_dostawy": [("pyta, kiedy dotrze zamówienie, bo przesyłka się opóźnia", (1, 3)),
                             ("chce zmienić adres dostawy w złożonym zamówieniu", (1,)),
                             ("kurier nie dostarczył paczki mimo statusu „doręczono”", (2, 3))],
    "reklamacje_i_zwroty": [("produkt przyszedł uszkodzony albo przestał działać po kilku dniach", (1, 2)),
                            ("chce zwrócić produkt w ustawowym terminie", (1,)), ("otrzymał inny produkt niż zamówił", (1,))],
    "platnosci_i_faktury": [("pieniądze zostały pobrane dwa razy za to samo zamówienie", (1, 3)),
                            ("prosi o fakturę VAT na firmę albo o jej korektę", (0, 1)),
                            ("płatność nie przeszła i nie da się opłacić zamówienia", (2, 3))],
    "wsparcie_techniczne": [("nie może zalogować się do konta lub aplikacji", (2, 3)),
                            ("usługa internetowa albo aplikacja przestała działać", (3,)),
                            ("urządzenie nie łączy się z siecią mimo poprawnej konfiguracji", (2,)),
                            ("prosi o pomoc w zmianie ustawień konta, które działa poprawnie", (0, 1))],
    "inne": [("proponuje współpracę reklamową", (0,)), ("pyta o możliwość pracy w firmie", (0,)),
             ("dzieli się ogólną opinią o firmie", (0,))],
}
# What must follow from the text for the level to be unambiguous.
URGENCY_HINTS = {
    0: ["To tylko pytanie lub informacja — klient niczego nie potrzebuje pilnie i nic go nie blokuje."],
    1: ["Klient prosi o załatwienie sprawy, ale może normalnie korzystać z usługi i nie wspomina o pośpiechu."],
    2: ["Z treści jasno wynika, że klient jest zablokowany: nie może zamówić, zapłacić albo skorzystać z usługi."],
    3: ["Klient pisze, że przez ten problem stoi praca jego firmy i traci pieniądze z każdą godziną.",
        "Klient zapowiada, że jeśli sprawa nie zostanie załatwiona, skieruje ją do sądu albo opisze w mediach.",
        "Klient pisze, że potrzebuje rozwiązania jeszcze dziś, bo jutro będzie za późno."],
}


def amount_pl(rng, lo, hi):
    """Random amount in złoty with a space as the thousands separator, e.g. '12 500 zł'."""
    return f"{rng.randrange(lo, hi):,}".replace(",", " ") + " zł"


def concrete_details(domain, rng):
    """Random names and numbers matching the domain, so that letters do not repeat the same data."""
    people = f"osoby {person(rng)} i {person(rng)}; firma „{rng.choice(COMPANIES)}” {rng.choice(COMPANY_FORMS)}; miejscowość {rng.choice(CITIES)}"
    if domain == "sad":
        details = (f"kwota sporu {amount_pl(rng, 2000, 480000)}; sygnatura akt {rng.choice(['I', 'II', 'III', 'IX', 'X'])} "
                   f"{rng.choice(['C', 'GC', 'Ns', 'Co', 'Ca', 'GNc'])} {rng.randrange(1, 3000)}/{rng.choice([24, 25, 26])}")
    elif domain == "adm":
        details = (f"znak sprawy {rng.choice(['UA', 'AB', 'WAB', 'IRIOŚ', 'GPN'])}.{rng.choice([6730, 6740, 6743])}."
                   f"{rng.randrange(1, 900)}.{rng.choice([2025, 2026])}; działka nr {rng.randrange(1, 900)}/{rng.randrange(1, 30)}")
    elif domain == "ksieg":
        details = (f"kwota {amount_pl(rng, 40, 60000)}; numer dokumentu FV/{rng.randrange(1, 900)}/{rng.randrange(1, 13):02d}/2026; "
                   f"NIP {rng.randrange(100, 999)}-{rng.randrange(100, 999)}-{rng.randrange(10, 99)}-{rng.randrange(10, 99)}")
    else:
        details = (f"jeśli pasuje: produkt lub usługa {rng.choice(PRODUCTS)}, numer zamówienia {rng.randrange(10000, 999999)}, "
                   f"kwota {amount_pl(rng, 20, 9000)}")
        people = f"klient {person(rng)}; sklep lub firma „{rng.choice(COMPANIES)}”"
    return f"Użyj tych danych (tylko tych, które pasują do dokumentu): {people}; {details}."


def clean(text):
    """Removes the markdown formatting the generator uses despite the ban."""
    text = re.sub(r"^```\w*\s*$", "", text, flags=re.M)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", text).strip().strip("`").strip()


def make_spec(domain, rng, i=None):
    """Draws the document type (evenly), then the variant; returns (description for the generator, labels)."""
    letter_date = dt.date(2026, 1, 5) + dt.timedelta(days=rng.randrange(330))
    if domain == "email":
        departments = sorted(EMAIL_SCENARIOS)
        department = departments[i % len(departments)] if i is not None else rng.choice(departments)
        resign = rng.random() < 0.25
        upset = rng.random() < 0.4
        scenario, levels = rng.choice(EMAIL_SCENARIOS[department])
        urgency = rng.choice(levels)
        desc = (f"E-mail od klienta do sklepu internetowego lub firmy usługowej, wysłany {date_pl(letter_date)}\n"
                f"O czym pisze klient: {scenario}.\n"
                + ("Klient wprost pisze, że rezygnuje z usługi, wypowiada umowę albo chce zamknąć konto.\n" if resign
                   else "Klient w ogóle nie wspomina o rezygnacji, wypowiedzeniu umowy ani zamknięciu konta.\n")
                + ("Klient jest wyraźnie zdenerwowany i to widać w tonie wiadomości.\n" if upset
                   else "Klient pisze spokojnie i uprzejmie.\n")
                + f"Pilność sprawy: {URGENCY_EMAIL[urgency]}. {rng.choice(URGENCY_HINTS[urgency])}")
        return desc, {"dzial": department, "rezygnacja": resign, "zdenerwowany": upset, "pilnosc": urgency}

    doc_types = sorted({p[0] for p in RECIPES[domain]})
    doc_type = doc_types[i % len(doc_types)] if i is not None else rng.choice(doc_types)
    _, variant, deadline, urgency = rng.choice([p for p in RECIPES[domain] if p[0] == doc_type])
    variant = variant.format(**{f"d{n}": date_pl(letter_date + dt.timedelta(days=n)) for n in (3, 5, 10, 40)})
    desc = (f"Dokument skierowany do {RECIPIENT[domain]}, datowany {date_pl(letter_date)}\n"
            f"Rodzaj: {DOCUMENT_TYPES[domain][doc_type]}.\nSzczegóły, które MUSZĄ wynikać z treści: {variant}.")
    labels = {"rodzaj": doc_type, "termin": deadline, "pilnosc": urgency}
    if domain == "ksieg":
        cat = rng.choice([k for k in COST_CATEGORIES if k != "nie_dotyczy"]) if doc_type in COST_DOCUMENT_TYPES else "nie_dotyczy"
        if cat != "nie_dotyczy":
            desc += f"\nZakup dotyczy kategorii: {COST_CATEGORIES[cat]}."
        labels["kategoria_kosztu"] = cat
    return desc, labels


_URGENT_RE = re.compile(r"\bpiln|natychmiast|niezwłoczn|bezzwłoczn|jak najszybciej|w trybie pilnym", re.I)
_BLOCKED_RE = re.compile(r"nie (mogę|moge|możemy|da się|jestem w stanie|jesteśmy w stanie|mam dostępu)|uniemożliwi|zablokowan", re.I)
_CRITICAL_RE = re.compile(r"\bsąd|sądow|\bmedi|\bpras|przestój|\bstoi\b|\bstoją\b|tracę|tracimy|traci\b|dziś|dzisiaj", re.I)
_NO_URGENCY_RULE = ("Nie używaj słów „pilne”, „natychmiast”, „niezwłocznie”, „jak najszybciej” — klient może spokojnie "
                    "poczekać na odpowiedź, nawet jeśli jest niezadowolony. Niezadowolenie to nie pilność.")


def urgency_problems(text, urgency):
    """E-mail: does the text unambiguously match the urgency level (SPEC.md)? Returns a list of problems."""
    problems = []
    if urgency <= 1 and _URGENT_RE.search(text):
        problems.append("urgency words at low/medium level")
    if urgency <= 1 and _BLOCKED_RE.search(text):
        problems.append("customer blocked at low/medium level")
    if urgency <= 2 and re.search(r"\bsąd|sądow|\bmedi|\bpras|przestój", text, re.I):
        problems.append("threat of court/media or downtime below critical")
    if urgency == 2 and not _BLOCKED_RE.search(text):
        problems.append("high level, but no blockage visible")
    if urgency == 3 and not _CRITICAL_RE.search(text):
        problems.append("critical level, but no damage/court/deadline today visible")
    return problems


_THREAT_RE = re.compile(r"\bsąd|sądow|\bmedi|\bpras|rzecznik|UOKiK|opinii publicznej|publicznie opisz", re.I)


def email_rules(text, labels):
    """Rules from SPEC.md (2026-10-18): a threat of court/media ⇒ upset. Returns the corrected labels."""
    if _THREAT_RE.search(text) and not labels["zdenerwowany"]:
        labels = {**labels, "zdenerwowany": True}
    return labels


def generate_one(url, job):
    domain, split, i, seed = job
    rng = random.Random(seed)
    desc, labels = make_spec(domain, rng, i)
    if domain == "email" and labels["pilnosc"] <= 1:
        desc += "\n" + _NO_URGENCY_RULE
    prompt = (f"Napisz realistyczny polski dokument według opisu.\n\n{desc}\n\n{concrete_details(domain, rng)}\n\n"
              "Wymagania:\n"
              "- 3–8 zdań; data dokumentu musi być podana w treści (w nagłówku albo w pierwszym zdaniu);\n"
              "- NIE dodawaj adresatowi żadnych innych obowiązków, terminów ani dat do wykonania czegoś "
              "poza tymi wynikającymi z opisu;\n"
              "- nie nazywaj wprost kategorii z opisu, jeśli prawdziwy dokument by tego nie zrobił;\n"
              "- zwróć wyłącznie treść dokumentu, bez komentarzy i bez formatowania markdown.")
    for attempt in range(4):  # e-mail inconsistent with its urgency → new attempt (other seed), then flagged
        res = post(url + "/v1/chat/completions", {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 450, "temperature": 0.9, "seed": seed + attempt * 7919,
            "chat_template_kwargs": {"enable_thinking": False},
        })
        text = clean(res["choices"][0]["message"]["content"])
        problems = urgency_problems(text, labels["pilnosc"]) if domain == "email" else []
        if not problems:
            break
    if domain == "email":
        labels = email_rules(text, labels)
    return {"id": f"{domain}-{split}-{i:03d}", "domain": domain, "split": split, "description": desc,
            "state": text, "questions": questions(domain), "expected": labels, "reviewed": False,
            **({"generation_problems": problems} if problems else {})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:9934")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--domains", default="sad,adm,ksieg,email")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for domain in args.domains.split(","):
        for split, n in SPLITS.items():
            path = OUT / f"{domain}_{split}.jsonl"
            done = {json.loads(l)["id"] for l in path.read_text(encoding="utf-8").splitlines()} if path.exists() else set()
            base = {"test": 1_000_000, "dev": 2_000_000}[split] + 10_000 * list(SPLITS).index(split)
            jobs = [(domain, split, i, base + ["sad", "adm", "ksieg", "email"].index(domain) * 1000 + i) for i in range(n)
                    if f"{domain}-{split}-{i:03d}" not in done]
            with path.open("a", encoding="utf-8") as f, ThreadPoolExecutor(args.workers) as ex:
                for row in ex.map(lambda j: generate_one(args.url, j), jobs):
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    f.flush()
            print(f"{domain}/{split}: {n}", flush=True)


if __name__ == "__main__":
    main()
