"""Pobiera prawdziwe orzeczenia sądów powszechnych z SAOS (saos.org.pl) jako pisma do benchmarku i treningu.

  python3 saos.py --ile 300                                        # data/real/saos.jsonl (trening)
  python3 saos.py --ile 120 --out saos_test.jsonl --pomin saos.jsonl  # test, bez orzeczeń z treningu

Orzeczenia to dokumenty urzędowe (art. 4 pr. aut.), w SAOS już zanonimizowane. Zapisujemy początek
(nagłówek + sentencja) i pouczenie, jeśli występuje — tak wygląda to, co kancelaria czyta na pierwszej stronie.
"""
import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://www.saos.org.pl/api/search/judgments"
REAL = Path(__file__).parent / "data" / "real"
TYP = {"DECISION": "postanowienie", "SENTENCE": "wyrok"}
# Wydziały cywilne, gospodarcze, pracy — tam kancelarie dostają najwięcej pism.
ZAPYTANIA = [("DECISION", "CIVIL"), ("SENTENCE", "CIVIL"), ("DECISION", "LABOUR_SOCIAL"), ("SENTENCE", "LABOUR_SOCIAL")]


def get(params):
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params),
                                 headers={"Accept": "application/json", "User-Agent": "jerzyk-bench/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fragment(tekst, n=1600):
    tekst = re.sub(r"<[^>]+>", " ", tekst)
    tekst = re.sub(r"[ \t]+", " ", tekst).strip()
    poczatek = tekst[:n]
    m = re.search(r"POUCZENIE.{0,700}", tekst[n:], re.S | re.I)
    return poczatek + ("\n[...]\n" + m.group(0) if m else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ile", type=int, default=300)
    ap.add_argument("--out", default="saos.jsonl", help="plik w data/real/")
    ap.add_argument("--pomin", nargs="*", default=[], help="pliki w data/real/ z orzeczeniami do pominięcia")
    args = ap.parse_args()
    OUT = REAL / args.out
    OUT.parent.mkdir(parents=True, exist_ok=True)
    widziane = set()
    for plik in [args.out] + args.pomin:  # rozłączność treningu i testu
        if (REAL / plik).exists():
            widziane |= {json.loads(l)["saos_id"] for l in (REAL / plik).read_text().splitlines()}
    na_zapytanie = args.ile // len(ZAPYTANIA)
    with OUT.open("a") as f:
        for typ, kategoria in ZAPYTANIA:
            zapisane, strona = 0, 0
            while zapisane < na_zapytanie:
                d = get({"pageSize": 50, "pageNumber": strona, "courtType": "COMMON", "judgmentTypes": typ, "judgmentDateFrom": "2024-01-01",
                         "sortingField": "JUDGMENT_DATE", "sortingDirection": "DESC",
                         "all": "cywilny" if kategoria == "CIVIL" else "pracy"})
                if not d["items"]:
                    break
                for it in d["items"]:
                    if it["id"] in widziane or len(it.get("textContent", "")) < 400 or zapisane >= na_zapytanie:
                        continue
                    widziane.add(it["id"])
                    f.write(json.dumps({
                        "saos_id": it["id"], "zrodlo": f"https://www.saos.org.pl/judgments/{it['id']}",
                        "sygnatura": it["courtCases"][0]["caseNumber"], "data": it["judgmentDate"],
                        "rodzaj_saos": TYP[typ], "state": fragment(it["textContent"]),
                    }, ensure_ascii=False) + "\n")
                    zapisane += 1
                strona += 1
                time.sleep(0.5)  # nie obciążamy serwisu
            print(f"{typ}/{kategoria}: {zapisane}", flush=True)


if __name__ == "__main__":
    main()
