"""Real rulings from 2025–2026 (data/prawo/saos-od-2025, see scripts/fetch_legal_sources.py) → dev set and training pool for v3.

  python -m scripts.build_saos_dev      # data/bench/sad_real_dev.jsonl + data/real/saos_2025_train.jsonl

- We exclude rulings from data/real/saos.jsonl (training v1/v2) and saos_test.jsonl (test) — the test set stays untouched.
- The answer is only the document type (certain from SAOS metadata): SENTENCE → wyrok, DECISION → postanowienie.
  Reasons (REASONS) and administrative orders (REGULATION) are skipped — SPEC.md has no unambiguous category for them yet.
- Dev: 60 sentences (wyrok) and 60 decisions (postanowienie). Training pool: the rest, also balanced (decisions are ~10× fewer).
"""
import argparse
import gzip
import json
import random
from pathlib import Path

from jerzyk.questions import questions
from scripts.fetch_saos import excerpt

ROOT = Path(__file__).resolve().parent.parent
TYPE_LABELS = {"SENTENCE": "wyrok", "DECISION": "postanowienie"}
DEV_PER_TYPE = 60


def main():
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    seen = {json.loads(line)["saos_id"] for name in ("saos.jsonl", "saos_test.jsonl")
            for line in (ROOT / "data" / "real" / name).read_text(encoding="utf-8").splitlines()}
    pool = {label: [] for label in TYPE_LABELS.values()}
    for path in sorted((ROOT / "data" / "prawo" / "saos-od-2025").glob("*.jsonl.gz")):
        for line in gzip.open(path, "rt", encoding="utf-8"):
            item = json.loads(line)
            if item["id"] in seen or item["judgmentType"] not in TYPE_LABELS or len(item.get("textContent", "")) < 400:
                continue
            pool[TYPE_LABELS[item["judgmentType"]]].append({
                "saos_id": item["id"], "source": f"https://www.saos.org.pl/judgments/{item['id']}",
                "case_number": item["courtCases"][0]["caseNumber"], "date": item["judgmentDate"],
                "saos_type": TYPE_LABELS[item["judgmentType"]], "state": excerpt(item["textContent"])})
    rng = random.Random(2025)
    dev, train = [], []
    for kind, rows in pool.items():
        rng.shuffle(rows)
        dev += rows[:DEV_PER_TYPE]
        train += rows[DEV_PER_TYPE:]
    q = {"rodzaj": questions("sad")["rodzaj"]}
    with (ROOT / "data" / "bench" / "sad_real_dev.jsonl").open("w", encoding="utf-8") as f:
        for i, r in enumerate(dev):
            f.write(json.dumps({"id": f"sad_real_dev-{i:03d}", "domain": "sad_real", "source": r["source"],
                                "state": r["state"], "questions": q, "expected": {"rodzaj": r["saos_type"]},
                                "reviewed": True}, ensure_ascii=False) + "\n")
    with (ROOT / "data" / "real" / "saos_2025_train.jsonl").open("w", encoding="utf-8") as f:
        for r in train:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"dev {len(dev)}; training pool: " + ", ".join(f"{k} {sum(r['saos_type'] == k for r in train)}" for k in pool))


if __name__ == "__main__":
    main()
