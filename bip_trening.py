"""Prawdziwe pisma urzędowe do TRENINGU v4 — z urzędów, których nie ma w teście (data/bench/adm_real_test.jsonl).

  python3 bip_trening.py adresy      # przeszukuje strony urzędów → data/real/bip_urls_train.txt
  .venv/bin/python bip.py data/real/bip_urls_train.txt data/real/bip_train.jsonl
  python3 bip_trening.py etykiety    # reguły → data/real/bip_train_etykiety.jsonl (do train_v1.py build)

Etykiety z reguł (jak przy SAOS: tylko to, co pewne):
- termin/pilność: „w terminie N dni” (także słownie) w zdaniu z działaniem strony (uwagi, zapoznać, odwołanie, zażalenie,
  wnioski, sprzeciw). Fikcja doręczenia („uważa się za dokonane po upływie 14 dni”) nie jest terminem (SPEC.md).
  Brak takiego zdania i brak „do dnia …” → termin NIE, pilność 0. Niejednoznaczne (data „do dnia”) → pomijamy pytanie.
- rodzaj: z tytułu — obwieszczenie/zawiadomienie o wszczęciu/zebraniu/wydaniu/przedłużeniu → zawiadomienie;
  polowania, konsultacje planów ogólnych → pomijamy pytanie o rodzaj (w teście „inne”, mało przykładów).
"""
import json
import re
import sys
import time
import urllib.request
from collections import deque
from pathlib import Path

ROOT = Path(__file__).parent
UA = {"User-Agent": "Mozilla/5.0 (jerzyk-bench; badania)"}
HOST = "https://samorzad.gov.pl"
# Strony startowe urzędów spoza testu (znalezione wyszukiwarką 2026-10-18).
START = [
    "/web/gmina-kobior/obwieszczenia", "/web/gmina-skorzec/ogloszenia3", "/web/gmina-pokrzywnica",
    "/web/gmina-zabrodzie/ogloszenia-i-komunikaty", "/web/gmina-branszczyk/obwieszczenia",
    "/web/powiat-losicki/decyzje-o-zezwoleniu-na-realizacje-inwestycji-drogowej",
    "/web/powiat-olesnicki/obwieszczenia-dot-zrid---2024-rok", "/web/gmina-jaslo/obwieszczenia-zawiadomienia",
    "/web/gmina-lutomiersk/warunki-zabudowy-i-zagospodarowania-przestrzennego", "/web/gmina-lutomiersk/obwieszczenia-ogloszenia-zp",
    "/web/gmina-rojewo", "/web/gmina-siepraw", "/web/powiat-zambrowski", "/web/powiat-sokolowski", "/web/powiat-ostrowiecki",
    "/web/powiat-nowomiejski", "/web/gmina-bobowa/ogloszenia-i-obwieszczenia", "/web/gmina-luzino/zagospodarowanie-przestrzenne",
    "/web/gmina-lubenia", "/web/gmina-skorzec", "/web/powiat-swiebodzinski", "/web/powiat-lipski", "/web/gmina-zabrodzie",
]
PISMO = re.compile(r"obwieszcz|zawiadom|decyzj|postanowien|wszczeci|zebrani|przedluzeni", re.I)
LISTA = re.compile(r"obwieszczenia|ogloszenia|zawiadomienia|komunikaty|warunki-zabudowy|zagospodarowanie|planowanie|decyzje|rok-20|20\d\d$", re.I)
NA_URZAD, STRON_NA_URZAD = 30, 25


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def adresy():
    test = {json.loads(l)["zrodlo"].split("/")[4] for l in (ROOT / "data/bench/adm_real_test.jsonl").read_text().splitlines()}
    stare = set((ROOT / "data/real/bip_urls.txt").read_text().split()) | set((ROOT / "data/real/bip_urls_v2.txt").read_text().split())
    wynik = []
    for start in START:
        slug = start.split("/")[2]
        if slug in test:
            continue
        kolejka, odwiedzone, pisma = deque([start]), set(), []
        while kolejka and len(odwiedzone) < STRON_NA_URZAD and len(pisma) < NA_URZAD:
            strona = kolejka.popleft()
            if strona in odwiedzone:
                continue
            odwiedzone.add(strona)
            try:
                html = get(HOST + strona)
            except Exception:
                continue
            for href in re.findall(rf'href="(/web/{re.escape(slug)}/[^"#?]+)"', html):
                ost = href.rstrip("/").split("/")[-1]
                url = HOST + href
                if PISMO.search(ost) and len(ost) > 25 and url not in stare and url not in pisma:
                    pisma.append(url)
                elif LISTA.search(ost) and href not in odwiedzone:
                    kolejka.append(href)
            time.sleep(0.7)
        wynik += [u for u in pisma[:NA_URZAD] if u not in wynik]
        print(f"{slug}: {len(pisma[:NA_URZAD])}", flush=True)
    (ROOT / "data/real/bip_urls_train.txt").write_text("\n".join(wynik) + "\n")
    print(f"razem {len(wynik)}")


SLOWNIE = {"trzech": 3, "siedmiu": 7, "czternastu": 14, "dwudziestu jeden": 21, "trzydziestu": 30, "tygodnia": 7}
_N = r"(\d{1,3}|trzech|siedmiu|czternastu|dwudziestu\s+jeden|trzydziestu|tygodnia)\s*(?:\(\w+\)\s*)?dni"
TERMIN = re.compile(rf"(?:(?:w\s+(?:nieprzekraczalnym\s+)?terminie|\btermin|w\s+ciągu)\s+(?:nie\s+krótszym\s+niż\s+)?{_N}"
                    rf"|{_N}\s+od\s+(?:dnia|daty))", re.I)
DZIALANIE = re.compile(r"uwag|zapozna|odwołan|zażaleni|wniosk|sprzeciw|wypowiedz|skarg|zastrzeże|ponagleni", re.I)
FIKCJA = re.compile(r"uważa\s+się\s+za\s+dokonane|uznaje\s+się\s+za\s+doręczon|doręczenie\s+uważa", re.I)


def etykiety_pisma(r):
    t = re.sub(r"\s+", " ", r["state"])
    dni = []
    for m in TERMIN.finditer(t):
        zdanie = t[max(0, m.start() - 500): m.end() + 150]
        if DZIALANIE.search(zdanie) and not FIKCJA.search(t[max(0, m.start() - 80): m.end() + 40]):
            g = re.sub(r"\s+", " ", (m.group(1) or m.group(2)).lower())
            dni.append(int(g) if g.isdigit() else SLOWNIE[g])
    e = {}
    tytul = r["tytul"].lower()
    if re.search(r"polowa|konsultac|przystapieniu do sporzadzania|plan ogolny", tytul):
        return None  # mało przykładów, w teście „inne” — nie uczymy z reguł
    if re.search(r"obwieszcz|zawiadom", tytul) and re.search(r"wszczeci|zebrani|wydaniu|wydanej|przedluzeni|zakonczeni|"
                                                               r"zawieszeni|podjeci|przekazaniu|ogledzin|decyzj|postanowien", tytul):
        e["rodzaj"] = "zawiadomienie"
    if dni:
        n = min(dni)
        e["termin"], e["pilnosc"] = True, 3 if n <= 7 else 2 if n <= 14 else 1
    elif not re.search(r"do\s+dnia\s+\d|niezwłocznie", t, re.I):
        e["termin"], e["pilnosc"] = False, 0
    return e or None


def etykiety():
    rows = [json.loads(l) for l in (ROOT / "data/real/bip_train.jsonl").read_text().splitlines()]
    out = []
    for r in rows:
        e = etykiety_pisma(r)
        if e:
            out.append({"zrodlo": r["zrodlo"], "state": r["state"], "expected": e})
    (ROOT / "data/real/bip_train_etykiety.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out))
    from collections import Counter
    print(len(rows), "pism →", len(out), "z etykietami;",
          "termin", Counter(x["expected"].get("termin") for x in out), "pilność", Counter(x["expected"].get("pilnosc") for x in out),
          "rodzaj", Counter(x["expected"].get("rodzaj") for x in out))


if __name__ == "__main__":
    {"adresy": adresy, "etykiety": etykiety}[sys.argv[1]]()
