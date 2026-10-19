"""Przegląd pism testowych w terminalu: pismo + odpowiedź wzorcowa → zgadzasz się czy nie.

  python3 review.py                 # losowe 30 nieprzejrzanych pism ze wszystkich dziedzin
  python3 review.py --domena adm --ile 10
  python3 review.py --flagi            # najpierw pisma oznaczone przez precheck.py

Klawisze: Enter = odpowiedź poprawna · n = błędna (wpisz uwagę) · s = pomiń · q = zakończ.
Wynik zapisywany od razu do data/bench/*_test.jsonl (pola przejrzane, ok, uwaga).
"""
import argparse
import json
import random
import textwrap
from pathlib import Path

BENCH = Path(__file__).parent / "data" / "bench"


def load(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def save(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domena")
    ap.add_argument("--ile", type=int, default=30)
    ap.add_argument("--flagi", action="store_true", help="najpierw pisma z flagami z precheck.py")
    args = ap.parse_args()

    pliki = sorted(BENCH.glob(f"{args.domena or '*'}_test.jsonl"))
    dane = {p: load(p) for p in pliki}
    kolejka = [(p, i) for p, rows in dane.items() for i, r in enumerate(rows) if not r.get("przejrzane")]
    random.Random().shuffle(kolejka)
    if args.flagi:  # najpierw pisma oznaczone przez precheck.py
        kolejka.sort(key=lambda pi: not dane[pi[0]][pi[1]].get("flagi"))
    kolejka = kolejka[:args.ile]

    for n, (p, i) in enumerate(kolejka, 1):
        r = dane[p][i]
        print("\n" + "=" * 80)
        print(f"[{n}/{len(kolejka)}] {r['id']}\n")
        for line in r["state"].splitlines():
            print(textwrap.fill(line, 80) if line.strip() else "")
        print("\n--- odpowiedź wzorcowa ---")
        for k, v in r["expected"].items():
            if k == "pilnosc":
                v = f"{v} – {r['questions']['pilnosc']['criteria'][v]}"
            print(f"  {k}: {v}")
        if r.get("flagi"):
            print("\n--- uwagi automatycznej kontroli ---")
            for fl in r["flagi"]:
                print(f"  ! {fl}")
        odp = input("\n[Enter] OK · [n] błędna · [s] pomiń · [q] koniec > ").strip().lower()
        if odp == "q":
            break
        if odp == "s":
            continue
        r["przejrzane"] = True
        r["ok"] = odp != "n"
        if not r["ok"]:
            r["uwaga"] = input("Co jest nie tak? > ").strip()
        save(p, dane[p])

    przejrzane = [r for rows in dane.values() for r in rows if r.get("przejrzane")]
    bledne = [r for r in przejrzane if not r.get("ok")]
    print(f"\nPrzejrzane: {len(przejrzane)}, błędne: {len(bledne)}")


if __name__ == "__main__":
    main()
