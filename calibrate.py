"""Skalowanie temperatury na zbiorze dev (osobno dla choice / noul / score) — żeby „90%” znaczyło 90%.

  USE_TF=0 .venv/bin/python calibrate.py --model models/jerzyk-v3 data/bench/*_dev.jsonl
  → models/jerzyk-v3.kalibracja.json  {"choice": T, "noul": T, "score": T}

laya-train kalibruje na wycinku danych treningowych (in-sample), więc pewność wychodzi zawyżona. Tu dopasowujemy
jedną temperaturę na typ pytania na pismach, których model nie widział: p_i ∝ p_i^(1/T). T > 1 obniża pewność.
evaluate.py i jerzyk_serve.py stosują plik, jeśli istnieje obok modelu.
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from evaluate import ask_laya

SIATKA = [round(0.25 + 0.05 * i, 2) for i in range(96)]  # 0.25 … 5.0


def skaluj(p, t):
    w = {k: max(v, 1e-9) ** (1 / t) for k, v in p.items()}
    s = sum(w.values())
    return {k: v / s for k, v in w.items()}


def plik_kalibracji(model):
    return Path(str(model).rstrip("/") + ".kalibracja.json")


def wczytaj(model):
    f = plik_kalibracji(model)
    return json.loads(f.read_text()) if f.exists() else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--model", required=True)
    args = ap.parse_args()
    rows = [json.loads(l) for f in args.files for l in Path(f).read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r.get("ok", True)]
    dane = defaultdict(list)  # typ → [(probs, gold)]
    for r in rows:
        probs = ask_laya(args.model, r["state"], r["questions"])
        for qid, q in r["questions"].items():
            dane[q["type"]].append((probs[qid], r["expected"][qid]))
    wynik = {}
    for typ, pary in dane.items():
        nll = lambda t: -sum(math.log(max(skaluj(p, t).get(g, 0), 1e-9)) for p, g in pary) / len(pary)
        wynik[typ] = min(SIATKA, key=nll)
        print(f"{typ}: n={len(pary)}  T={wynik[typ]}  NLL {nll(1.0):.3f} → {nll(wynik[typ]):.3f}", flush=True)
    plik_kalibracji(args.model).write_text(json.dumps(wynik, indent=2))
    print(f"zapisano {plik_kalibracji(args.model)}")


if __name__ == "__main__":
    main()
