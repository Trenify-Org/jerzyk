"""Automatyczna kontrola zbioru testowego przed przeglądem ręcznym: oznacza pisma podejrzane o niezgodność z odpowiedzią.

  python3 precheck.py --url http://127.0.0.1:9934     # dopisuje pole "flagi" w data/bench/*_{test,dev}.jsonl

Sprawdzenia:
- reguły: czy pismo zawiera termin, gdy odpowiedź mówi „termin: tak” (i odwrotnie), czy długość terminu pasuje
  do pilności, czy w piśmie jest data, czy tekst nie jest za krótki / ucięty,
- Bielik: czy jego odczyt rodzaju (dla e-maili: działu) zgadza się z odpowiedzią wzorcową.
Pismo z flagą trafia do przeglądu w pierwszej kolejności (review.py --flagi).
"""
import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import deadlines
from bench import letter_probs
from train_v1 import _sprawdz

BENCH = Path(__file__).parent / "data" / "bench"
DNI = re.compile(r"(\d{1,3}|siedmiu|czternastu|tygodnia|dwóch tygodni|trzydziestu|dwudziestu jeden)\s*(dni|tygodni)?", re.I)
SLOWNIE = {"siedmiu": 7, "tygodnia": 7, "czternastu": 14, "dwóch tygodni": 14, "dwudziestu jeden": 21, "trzydziestu": 30}


def dlugosc_terminu(tekst):
    """Najkrótszy termin w dniach zapisany w piśmie jako „w terminie N dni / tygodnia …” (albo None)."""
    wyniki = []
    for m in re.finditer(r"(?:w\s+(?:nieprzekraczalnym\s+)?terminie|w\s+ciągu)\s+(\d{1,3}|siedmiu|czternastu|tygodnia|"
                         r"dwóch\s+tygodni|dwudziestu\s+jeden|trzydziestu)(?:\s+dni)?", tekst, re.I):
        s = re.sub(r"\s+", " ", m.group(1).lower())
        wyniki.append(int(s) if s.isdigit() else SLOWNIE.get(s))
    return min([w for w in wyniki if w], default=None)


def reguly(r):
    flagi = list(r.get("problemy_generacji", []))
    t, e = r["state"], r["expected"]
    if len(t) < 150:
        flagi.append("za krótki")
    if r["domena"] != "email":
        if not (deadlines._DATE_WORDS.search(t) or deadlines._DATE_DIGITS.search(t)):
            flagi.append("brak daty w piśmie")
        n = dlugosc_terminu(t)
        daty = [x for x in deadlines.find(t) if x.kind == "date"]
        if e["termin"] and n is None and not daty and "niezwłocznie" not in t.lower():
            flagi.append("termin=tak, ale nie widać terminu")
        if not e["termin"] and n is not None:
            flagi.append(f"termin=nie, ale w piśmie jest termin {n} dni")
        if e["termin"] and n is not None:
            oczek = 3 if n <= 7 else 2 if n <= 14 else 1
            if oczek != e["pilnosc"]:
                flagi.append(f"pilność {e['pilnosc']}, a termin {n} dni sugeruje {oczek}")
    return flagi


def _sprawdz_tak_nie(url, r):
    """E-maile: czy Bielik widzi rezygnację i zdenerwowanie tak jak odpowiedź wzorcowa."""
    r["flagi_tak_nie"] = []
    for qid in ("rezygnacja", "zdenerwowany"):
        p_tak = letter_probs(url, r["state"], r["questions"][qid]["instructions"], ["tak", "nie"])[0]
        if (p_tak >= 0.5) != r["expected"][qid]:
            r["flagi_tak_nie"].append(f"Bielik: {qid}={'tak' if p_tak >= 0.5 else 'nie'} ({p_tak:.2f})")
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:9934")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--od-nowa", action="store_true", help="sprawdź też pliki już sprawdzone")
    ap.add_argument("--pliki", default="*_test.jsonl,*_dev.jsonl", help="wzorce plików w data/bench (bez *_real_*)")
    args = ap.parse_args()
    sciezki = sorted({p for w in args.pliki.split(",") for p in BENCH.glob(w) if "_real_" not in p.name})
    for path in sciezki:
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        if all("flagi" in r for r in rows) and not args.od_nowa:
            continue  # plik już sprawdzony (wznowienie po przerwie)
        with ThreadPoolExecutor(args.workers) as ex:
            list(ex.map(lambda r: _sprawdz(args.url, r), rows))
        if path.name.startswith("email"):
            with ThreadPoolExecutor(args.workers) as ex:
                list(ex.map(lambda r: _sprawdz_tak_nie(args.url, r), rows))
        for r in rows:
            r["flagi"] = reguly(r) + r.pop("flagi_tak_nie", [])
            if not r.pop("zgodne"):
                qid = "dzial" if r["domena"] == "email" else "rodzaj"
                r["flagi"].append(f"Bielik czyta {qid} jako {r['bielik'][qid]} ({r['bielik']['p']})")
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        n = sum(bool(r["flagi"]) for r in rows)
        print(f"{path.name}: {n}/{len(rows)} z flagami", flush=True)


if __name__ == "__main__":
    main()
