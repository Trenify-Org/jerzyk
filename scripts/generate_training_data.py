"""Jerzyk v1 training data: answers from the recipes, letters written by Qwen, a Bielik consistency filter, and SAOS.

  .venv/bin/python -m scripts.generate_training_data gen    --url http://127.0.0.1:9932 --n 500   # Qwen writes: data/train_v1/{domain}.jsonl
  .venv/bin/python -m scripts.generate_training_data check  --url http://127.0.0.1:9934          # Bielik checks type/department: field consistent
  .venv/bin/python -m scripts.generate_training_data build                                        # data/train_v1/train.jsonl for laya-train

The test set is written by Bielik, the training set by Qwen — Jerzyk must not learn the style of the test set.
The answers follow from the recipe (jerzyk.questions.RECIPES), not from a model's judgement; Bielik only serves to
filter out letters that do not match the recipe.
"""
import argparse
import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from jerzyk.questions import questions
from scripts.generate_benchmark import generate_one
from scripts.llm import letter_probs

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "train_v1"
DOMAINS = ("sad", "adm", "ksieg", "email")
SEED0 = 5_000_000  # disjoint from the test set seeds (1–2 million)


def _rows(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []


def _write(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def cmd_gen(args):
    OUT.mkdir(parents=True, exist_ok=True)
    for domain in DOMAINS:
        path = OUT / f"{domain}.jsonl"
        done = {r["id"] for r in _rows(path)}
        jobs = [(domain, "train", i, SEED0 + DOMAINS.index(domain) * 100_000 + i) for i in range(args.n)
                if f"{domain}-train-{i:03d}" not in done]
        with path.open("a", encoding="utf-8") as f, ThreadPoolExecutor(args.workers) as ex:
            for n, row in enumerate(ex.map(lambda j: generate_one(args.url, j), jobs), 1):
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                if n % 50 == 0:
                    print(f"{domain}: {len(done) + n}/{args.n}", flush=True)


def check_with_bielik(url, row):
    """Does Bielik read the letter the way the recipe assumes (main choice question)?"""
    qid = "dzial" if row["domain"] == "email" else "rodzaj"
    q = row["questions"][qid]
    labels = [f"{k} – {v}" for k, v in q["criteria"].items()]
    p = dict(zip(q["criteria"], letter_probs(url, row["state"], q["instructions"], labels)))
    pred = max(p, key=p.get)
    row["bielik_reading"] = {qid: pred, "p": round(p[pred], 3)}
    row["consistent"] = pred == row["expected"][qid]
    return row


def cmd_check(args):
    for domain in DOMAINS:
        path = OUT / f"{domain}.jsonl"
        rows = _rows(path)
        todo = [r for r in rows if "consistent" not in r]
        with ThreadPoolExecutor(args.workers) as ex:
            list(ex.map(lambda r: check_with_bielik(args.url, r), todo))
        _write(path, rows)
        ok = sum(r["consistent"] for r in rows)
        print(f"{domain}: consistent {ok}/{len(rows)}", flush=True)


def cmd_build(args):
    out = []
    for domain in DOMAINS:
        for r in _rows(OUT / f"{domain}.jsonl"):
            if r.get("consistent") and not r.get("generation_problems"):
                out.append({"state": r["state"], "questions": questions(domain), "expected": r["expected"]})
    # SAOS: real court rulings; only the type answer is certain (no notes about deadlines).
    # v1 took all 300 (150 judgments + 150 decisions) and began to see a judgment in the letters of parties — v2 takes --saos of each.
    # v3: pool from saos.jsonl (2024–26) and saos_2025_train.jsonl (build_saos_dev.py; disjoint from test and dev), random, balanced.
    q_court = questions("sad")
    saos = _rows(ROOT / "data" / "real" / "saos.jsonl") + _rows(ROOT / "data" / "real" / "saos_2025_train.jsonl")
    rng = random.Random(args.seed)
    for doc_type in ("wyrok", "postanowienie"):
        chosen = [r for r in saos if r["saos_type"] == doc_type]
        rng.shuffle(chosen)
        for r in chosen[:args.saos]:
            out.append({"state": r["state"], "questions": {"rodzaj": q_court["rodzaj"]},
                        "expected": {"rodzaj": r["saos_type"]}})
    # v4: real official letters from offices outside the test set (notices_training_data.py), labels from rules; --notice-repeats copies.
    q_adm = questions("adm")
    for r in _rows(ROOT / "data" / "real" / "bip_train_etykiety.jsonl") * args.notice_repeats:
        out.append({"state": r["state"][:6000], "questions": {k: q_adm[k] for k in r["expected"]}, "expected": r["expected"]})
    _write(ROOT / args.out, out)
    print(f"{args.out}: {len(out)} letters", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gen", "check", "build"])
    ap.add_argument("--url", default="http://127.0.0.1:9932")
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--saos", type=int, default=40, help="build: how many judgments and how many decisions from SAOS")
    ap.add_argument("--out", default="data/train_v2/train.jsonl", help="build: output file")
    ap.add_argument("--seed", type=int, default=0, help="build: random draw of SAOS rulings")
    ap.add_argument("--notice-repeats", type=int, default=0,
                    help="build: how many times to add the real official letters (v4: 2)")
    args = ap.parse_args()
    {"gen": cmd_gen, "check": cmd_check, "build": cmd_build}[args.cmd](args)


if __name__ == "__main__":
    main()
