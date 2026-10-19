"""Dane treningowe Jerzyka v1: odpowiedzi z konstrukcji, pisma od Qwena, filtr zgodności Bielika, + SAOS.

  python3 train_v1.py gen    --url http://127.0.0.1:9932 --n 500   # Qwen pisze: data/train_v1/{domena}.jsonl
  python3 train_v1.py check  --url http://127.0.0.1:9934            # Bielik sprawdza rodzaj/dział: pole zgodne
  python3 train_v1.py build                                        # data/train_v1/train.jsonl dla laya-train

Test pisze Bielik, trening Qwen — Jerzyk nie może nauczyć się stylu zbioru testowego.
Odpowiedzi wynikają z przepisu (tasks.PRZEPISY), a nie z oceny modelu; Bielik służy tylko do odsiewu pism,
które nie zgadzają się z przepisem.
"""
import argparse
import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bench import letter_probs
from gen_bench import gen_one
from tasks import questions

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "train_v1"
DOMENY = ("sad", "adm", "ksieg", "email")
SEED0 = 5_000_000  # rozłączne z ziarnami zbioru testowego (1–2 mln)


def _rows(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


def _write(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def cmd_gen(args):
    OUT.mkdir(parents=True, exist_ok=True)
    for d in DOMENY:
        path = OUT / f"{d}.jsonl"
        done = {r["id"] for r in _rows(path)}
        jobs = [(d, "train", i, SEED0 + DOMENY.index(d) * 100_000 + i) for i in range(args.n)
                if f"{d}-train-{i:03d}" not in done]
        with path.open("a") as f, ThreadPoolExecutor(args.workers) as ex:
            for n, row in enumerate(ex.map(lambda j: gen_one(args.url, j), jobs), 1):
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                if n % 50 == 0:
                    print(f"{d}: {len(done) + n}/{args.n}", flush=True)


def _sprawdz(url, row):
    """Czy Bielik czyta pismo tak, jak zakłada przepis (główne pytanie choice)?"""
    qid = "dzial" if row["domena"] == "email" else "rodzaj"
    q = row["questions"][qid]
    labels = [f"{k} – {v}" for k, v in q["criteria"].items()]
    p = dict(zip(q["criteria"], letter_probs(url, row["state"], q["instructions"], labels)))
    pred = max(p, key=p.get)
    row["bielik"] = {qid: pred, "p": round(p[pred], 3)}
    row["zgodne"] = pred == row["expected"][qid]
    return row


def cmd_check(args):
    for d in DOMENY:
        path = OUT / f"{d}.jsonl"
        rows = _rows(path)
        todo = [r for r in rows if "zgodne" not in r]
        with ThreadPoolExecutor(args.workers) as ex:
            list(ex.map(lambda r: _sprawdz(args.url, r), todo))
        _write(path, rows)
        ok = sum(r["zgodne"] for r in rows)
        print(f"{d}: zgodne {ok}/{len(rows)}", flush=True)


def cmd_build(args):
    out = []
    for d in DOMENY:
        for r in _rows(OUT / f"{d}.jsonl"):
            if r.get("zgodne") and not r.get("problemy_generacji"):
                out.append({"state": r["state"], "questions": questions(d), "expected": r["expected"]})
    # SAOS: prawdziwe orzeczenia; pewna jest tylko odpowiedź o rodzaj (brak pouczeń o terminach).
    # v1 brał wszystkie 300 (150 wyroków + 150 postanowień) i zaczął widzieć wyrok w pismach stron — v2 bierze po --saos sztuk.
    # v3: pula z saos.jsonl (2024–26) i saos_2025_train.jsonl (saos_2025.py; rozłączna z testem i dev), losowo, wyrównana.
    q_sad = questions("sad")
    saos = _rows(ROOT / "data" / "real" / "saos.jsonl") + _rows(ROOT / "data" / "real" / "saos_2025_train.jsonl")
    rng = random.Random(args.seed)
    for rodzaj in ("wyrok", "postanowienie"):
        wybrane = [r for r in saos if r["rodzaj_saos"] == rodzaj]
        rng.shuffle(wybrane)
        for r in wybrane[:args.saos]:
            out.append({"state": r["state"], "questions": {"rodzaj": q_sad["rodzaj"]},
                        "expected": {"rodzaj": r["rodzaj_saos"]}})
    # v4: prawdziwe pisma urzędowe z urzędów spoza testu (bip_trening.py), etykiety z reguł; --bip-razy powtórzeń.
    q_adm = questions("adm")
    for r in _rows(ROOT / "data" / "real" / "bip_train_etykiety.jsonl") * args.bip_razy:
        out.append({"state": r["state"][:6000], "questions": {k: q_adm[k] for k in r["expected"]}, "expected": r["expected"]})
    _write(ROOT / args.out, out)
    print(f"{args.out}: {len(out)} pism", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gen", "check", "build"])
    ap.add_argument("--url", default="http://127.0.0.1:9932")
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--saos", type=int, default=40, help="build: ile wyroków i ile postanowień z SAOS")
    ap.add_argument("--out", default="data/train_v2/train.jsonl", help="build: plik wynikowy")
    ap.add_argument("--seed", type=int, default=0, help="build: losowanie orzeczeń SAOS")
    ap.add_argument("--bip-razy", type=int, default=0, help="build: ile razy dodać prawdziwe pisma urzędowe (v4: 2)")
    args = ap.parse_args()
    {"gen": cmd_gen, "check": cmd_check, "build": cmd_build}[args.cmd](args)


if __name__ == "__main__":
    main()
