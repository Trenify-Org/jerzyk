"""Generuje zbiory test/dev jerzyk-bench z odpowiedziami z konstrukcji (tasks.PRZEPISY).

  python3 gen_bench.py --url http://127.0.0.1:9934            # data/bench/{domena}_{split}.jsonl
"""
import argparse
import datetime as dt
import json
import random
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bench import post
from tasks import KATEGORIE_KOSZTU, KOSZTOWE, PILNOSC_EMAIL, PRZEPISY, RODZAJE, questions

OUT = Path(__file__).parent / "data" / "bench"
SPLITS = {"test": 120, "dev": 30}
MIESIACE = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
            "września", "października", "listopada", "grudnia"]
ODBIORCA = {
    "sad": "kancelarii prawnej (pełnomocnika strony)",
    "adm": "pracowni architektonicznej (projektanta lub pełnomocnika inwestora)",
    "ksieg": "biura rachunkowego (w imieniu klienta)",
}


IMIONA = ["Anna", "Piotr", "Katarzyna", "Tomasz", "Magdalena", "Marcin", "Agnieszka", "Paweł", "Joanna", "Krzysztof",
          "Ewa", "Michał", "Barbara", "Grzegorz", "Natalia", "Łukasz", "Monika", "Jakub", "Aleksandra", "Wojciech"]
NAZWISKA = ["Wiśniewski", "Wójcik", "Kamiński", "Lewandowski", "Zieliński", "Szymański", "Woźniak", "Dąbrowski",
            "Kozłowski", "Jankowski", "Mazur", "Krawczyk", "Piotrowski", "Grabowski", "Pawlak", "Michalski",
            "Zając", "Król", "Wieczorek", "Jabłoński", "Majewski", "Olszewski", "Stępień", "Malinowski", "Górski"]
FIRMY = ["Budrex", "Termo-Plan", "Agro-Vit", "Mostostal-Pom", "Nordis", "Kwadrat Studio", "Elmax", "Delta-Inwest",
         "Wodex", "Polbet", "Alfa-Med", "Trans-Kar", "Glob-Tech", "Sokół Development", "Ekoterm", "Retail-Point"]
MIASTA = ["Warszawa", "Kraków", "Gdańsk", "Wrocław", "Poznań", "Łódź", "Lublin", "Białystok", "Rzeszów", "Olsztyn",
          "Kielce", "Opole", "Toruń", "Szczecin", "Zielona Góra", "Katowice", "Bydgoszcz", "Koszalin", "Płock", "Nowy Sącz"]
FORMY = ["sp. z o.o.", "S.A.", "sp.j.", "sp.k."]


def data_pl(d):
    return f"{d.day} {MIESIACE[d.month - 1]} {d.year} r."


def osoba(rng):
    nazwisko = rng.choice(NAZWISKA)
    imie = rng.choice(IMIONA)
    if imie.endswith("a") and nazwisko.endswith("ski"):
        nazwisko = nazwisko[:-1] + "a"
    return f"{imie} {nazwisko}"


PRODUKTY = ["ekspres do kawy", "rower elektryczny", "pakiet internetu światłowodowego", "kurtka zimowa", "laptop",
            "abonament na oprogramowanie", "zestaw mebli ogrodowych", "karnet na siłownię", "smartfon", "odkurzacz",
            "kurs online", "opony zimowe", "konto firmowe", "hosting strony", "zestaw kosmetyków"]


# Scenariusze spójne z działem — losowanie działu i niepasującego produktu dawało sprzeczne e-maile.
# Scenariusz → dozwolone poziomy pilności (SPEC.md, skala e-maili). v1 losował pilność niezależnie od scenariusza,
# co dawało sprzeczne pary („pyta o pracę” + krytyczna) i szum w etykietach — stąd 44–54% u wszystkich modeli.
SCENARIUSZE_EMAIL = {
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
# Co musi wynikać z treści, żeby poziom był jednoznaczny.
WSKAZOWKI_PILNOSCI = {
    0: ["To tylko pytanie lub informacja — klient niczego nie potrzebuje pilnie i nic go nie blokuje."],
    1: ["Klient prosi o załatwienie sprawy, ale może normalnie korzystać z usługi i nie wspomina o pośpiechu."],
    2: ["Z treści jasno wynika, że klient jest zablokowany: nie może zamówić, zapłacić albo skorzystać z usługi."],
    3: ["Klient pisze, że przez ten problem stoi praca jego firmy i traci pieniądze z każdą godziną.",
        "Klient zapowiada, że jeśli sprawa nie zostanie załatwiona, skieruje ją do sądu albo opisze w mediach.",
        "Klient pisze, że potrzebuje rozwiązania jeszcze dziś, bo jutro będzie za późno."],
}


def zl(rng, lo, hi):
    return f"{rng.randrange(lo, hi):,}".replace(",", " ") + " zł"


def realia(domena, rng):
    """Losowe nazwy i liczby dopasowane do dziedziny, żeby pisma nie powtarzały tych samych danych."""
    ludzie = f"osoby {osoba(rng)} i {osoba(rng)}; firma „{rng.choice(FIRMY)}” {rng.choice(FORMY)}; miejscowość {rng.choice(MIASTA)}"
    if domena == "sad":
        szczegoly = (f"kwota sporu {zl(rng, 2000, 480000)}; sygnatura akt {rng.choice(['I', 'II', 'III', 'IX', 'X'])} "
                     f"{rng.choice(['C', 'GC', 'Ns', 'Co', 'Ca', 'GNc'])} {rng.randrange(1, 3000)}/{rng.choice([24, 25, 26])}")
    elif domena == "adm":
        szczegoly = (f"znak sprawy {rng.choice(['UA', 'AB', 'WAB', 'IRIOŚ', 'GPN'])}.{rng.choice([6730, 6740, 6743])}."
                     f"{rng.randrange(1, 900)}.{rng.choice([2025, 2026])}; działka nr {rng.randrange(1, 900)}/{rng.randrange(1, 30)}")
    elif domena == "ksieg":
        szczegoly = (f"kwota {zl(rng, 40, 60000)}; numer dokumentu FV/{rng.randrange(1, 900)}/{rng.randrange(1, 13):02d}/2026; "
                     f"NIP {rng.randrange(100, 999)}-{rng.randrange(100, 999)}-{rng.randrange(10, 99)}-{rng.randrange(10, 99)}")
    else:
        szczegoly = (f"jeśli pasuje: produkt lub usługa {rng.choice(PRODUKTY)}, numer zamówienia {rng.randrange(10000, 999999)}, "
                     f"kwota {zl(rng, 20, 9000)}")
        ludzie = f"klient {osoba(rng)}; sklep lub firma „{rng.choice(FIRMY)}”"
    return f"Użyj tych danych (tylko tych, które pasują do dokumentu): {ludzie}; {szczegoly}."


def czysc(tekst):
    """Usuwa formatowanie markdown, którego generator używa mimo zakazu."""
    tekst = re.sub(r"^```\w*\s*$", "", tekst, flags=re.M)
    tekst = tekst.replace("**", "").replace("__", "")
    tekst = re.sub(r"^#+\s*", "", tekst, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", tekst).strip().strip("`").strip()


def spec_pisma(domena, rng, i=None):
    """Losuje rodzaj (równomiernie), potem wariant; zwraca (opis dla generatora, etykiety)."""
    data = dt.date(2026, 1, 5) + dt.timedelta(days=rng.randrange(330))
    if domena == "email":
        dzialy = sorted(SCENARIUSZE_EMAIL)
        dzial = dzialy[i % len(dzialy)] if i is not None else rng.choice(dzialy)
        rez = rng.random() < 0.25
        zdenerw = rng.random() < 0.4
        scenariusz, poziomy = rng.choice(SCENARIUSZE_EMAIL[dzial])
        pil = rng.choice(poziomy)
        opis = (f"E-mail od klienta do sklepu internetowego lub firmy usługowej, wysłany {data_pl(data)}\n"
                f"O czym pisze klient: {scenariusz}.\n"
                + ("Klient wprost pisze, że rezygnuje z usługi, wypowiada umowę albo chce zamknąć konto.\n" if rez
                   else "Klient w ogóle nie wspomina o rezygnacji, wypowiedzeniu umowy ani zamknięciu konta.\n")
                + ("Klient jest wyraźnie zdenerwowany i to widać w tonie wiadomości.\n" if zdenerw
                   else "Klient pisze spokojnie i uprzejmie.\n")
                + f"Pilność sprawy: {PILNOSC_EMAIL[pil]}. {rng.choice(WSKAZOWKI_PILNOSCI[pil])}")
        return opis, {"dzial": dzial, "rezygnacja": rez, "zdenerwowany": zdenerw, "pilnosc": pil}

    rodzaje = sorted({p[0] for p in PRZEPISY[domena]})
    rodzaj = rodzaje[i % len(rodzaje)] if i is not None else rng.choice(rodzaje)
    _, wariant, termin, pil = rng.choice([p for p in PRZEPISY[domena] if p[0] == rodzaj])
    wariant = wariant.format(**{f"d{n}": data_pl(data + dt.timedelta(days=n)) for n in (3, 5, 10, 40)})
    opis = (f"Dokument skierowany do {ODBIORCA[domena]}, datowany {data_pl(data)}\n"
            f"Rodzaj: {RODZAJE[domena][rodzaj]}.\nSzczegóły, które MUSZĄ wynikać z treści: {wariant}.")
    labels = {"rodzaj": rodzaj, "termin": termin, "pilnosc": pil}
    if domena == "ksieg":
        kat = rng.choice([k for k in KATEGORIE_KOSZTU if k != "nie_dotyczy"]) if rodzaj in KOSZTOWE else "nie_dotyczy"
        if kat != "nie_dotyczy":
            opis += f"\nZakup dotyczy kategorii: {KATEGORIE_KOSZTU[kat]}."
        labels["kategoria_kosztu"] = kat
    return opis, labels


_PILNE = re.compile(r"\bpiln|natychmiast|niezwłoczn|bezzwłoczn|jak najszybciej|w trybie pilnym", re.I)
_BLOKADA = re.compile(r"nie (mogę|moge|możemy|da się|jestem w stanie|jesteśmy w stanie|mam dostępu)|uniemożliwi|zablokowan", re.I)
_KRYTYCZNE = re.compile(r"\bsąd|sądow|\bmedi|\bpras|przestój|\bstoi\b|\bstoją\b|tracę|tracimy|traci\b|dziś|dzisiaj", re.I)
_ZAKAZ_PILNOSCI = ("Nie używaj słów „pilne”, „natychmiast”, „niezwłocznie”, „jak najszybciej” — klient może spokojnie "
                   "poczekać na odpowiedź, nawet jeśli jest niezadowolony. Niezadowolenie to nie pilność.")


def zgodnosc_pilnosci(tekst, pil):
    """E-mail: czy treść jednoznacznie odpowiada poziomowi pilności (SPEC.md). Zwraca listę problemów."""
    p = []
    if pil <= 1 and _PILNE.search(tekst):
        p.append("słowa o pilności przy niskiej/średniej")
    if pil <= 1 and _BLOKADA.search(tekst):
        p.append("klient zablokowany przy niskiej/średniej")
    if pil <= 2 and re.search(r"\bsąd|sądow|\bmedi|\bpras|przestój", tekst, re.I):
        p.append("groźba sądu/mediów lub przestój poniżej krytycznej")
    if pil == 2 and not _BLOKADA.search(tekst):
        p.append("wysoka, ale nie widać blokady")
    if pil == 3 and not _KRYTYCZNE.search(tekst):
        p.append("krytyczna, ale nie widać szkody/sądu/terminu dziś")
    return p


_GROZBA = re.compile(r"\bsąd|sądow|\bmedi|\bpras|rzecznik|UOKiK|opinii publicznej|publicznie opisz", re.I)


def reguly_email(tekst, labels):
    """Reguły SPEC.md (2026-10-18): groźba sądu/mediów ⇒ zdenerwowany. Zwraca poprawione etykiety."""
    if _GROZBA.search(tekst) and not labels["zdenerwowany"]:
        labels = {**labels, "zdenerwowany": True}
    return labels


def gen_one(url, job):
    domena, split, i, seed = job
    rng = random.Random(seed)
    opis, labels = spec_pisma(domena, rng, i)
    if domena == "email" and labels["pilnosc"] <= 1:
        opis += "\n" + _ZAKAZ_PILNOSCI
    prompt = (f"Napisz realistyczny polski dokument według opisu.\n\n{opis}\n\n{realia(domena, rng)}\n\n"
              "Wymagania:\n"
              "- 3–8 zdań; data dokumentu musi być podana w treści (w nagłówku albo w pierwszym zdaniu);\n"
              "- NIE dodawaj adresatowi żadnych innych obowiązków, terminów ani dat do wykonania czegoś "
              "poza tymi wynikającymi z opisu;\n"
              "- nie nazywaj wprost kategorii z opisu, jeśli prawdziwy dokument by tego nie zrobił;\n"
              "- zwróć wyłącznie treść dokumentu, bez komentarzy i bez formatowania markdown.")
    for proba in range(4):  # e-mail niezgodny z pilnością → nowa próba (inne ziarno), potem flaga
        res = post(url + "/v1/chat/completions", {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 450, "temperature": 0.9, "seed": seed + proba * 7919,
            "chat_template_kwargs": {"enable_thinking": False},
        })
        tekst = czysc(res["choices"][0]["message"]["content"])
        problemy = zgodnosc_pilnosci(tekst, labels["pilnosc"]) if domena == "email" else []
        if not problemy:
            break
    if domena == "email":
        labels = reguly_email(tekst, labels)
    return {"id": f"{domena}-{split}-{i:03d}", "domena": domena, "split": split, "opis": opis,
            "state": tekst, "questions": questions(domena), "expected": labels, "przejrzane": False,
            **({"problemy_generacji": problemy} if problemy else {})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:9934")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--domeny", default="sad,adm,ksieg,email")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for domena in args.domeny.split(","):
        for split, n in SPLITS.items():
            path = OUT / f"{domena}_{split}.jsonl"
            done = {json.loads(l)["id"] for l in path.read_text().splitlines()} if path.exists() else set()
            base = {"test": 1_000_000, "dev": 2_000_000}[split] + 10_000 * list(SPLITS).index(split)
            jobs = [(domena, split, i, base + ["sad", "adm", "ksieg", "email"].index(domena) * 1000 + i) for i in range(n)
                    if f"{domena}-{split}-{i:03d}" not in done]
            with path.open("a") as f, ThreadPoolExecutor(args.workers) as ex:
                for row in ex.map(lambda j: gen_one(args.url, j), jobs):
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    f.flush()
            print(f"{domena}/{split}: {n}", flush=True)


if __name__ == "__main__":
    main()
