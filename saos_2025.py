"""Prawdziwe orzeczenia z 2025–2026 (data/prawo/saos-od-2025, prawo.py) → zbiór dev i pula treningowa dla v3.

  python3 saos_2025.py      # data/bench/sad_real_dev.jsonl + data/real/saos_2025_train.jsonl

- Wykluczamy orzeczenia z data/real/saos.jsonl (trening v1/v2) i saos_test.jsonl (test) — test zostaje nietknięty.
- Odpowiedź tylko o rodzaj (pewna z metadanych SAOS): SENTENCE → wyrok, DECISION → postanowienie.
  Uzasadnienia (REASONS) i zarządzenia (REGULATION) pomijamy — w SPEC.md nie mają jeszcze jednoznacznej kategorii.
- Dev: po 60 wyroków i postanowień. Pula treningowa: reszta, też wyrównana (postanowień jest ~10× mniej).
"""
import gzip
import json
import random
from pathlib import Path

from saos import fragment
from tasks import questions

ROOT = Path(__file__).parent
TYP = {"SENTENCE": "wyrok", "DECISION": "postanowienie"}
DEV_NA_RODZAJ = 60


def main():
    widziane = {json.loads(l)["saos_id"] for f in ("saos.jsonl", "saos_test.jsonl")
                for l in (ROOT / "data" / "real" / f).read_text().splitlines()}
    pula = {r: [] for r in TYP.values()}
    for f in sorted((ROOT / "data" / "prawo" / "saos-od-2025").glob("*.jsonl.gz")):
        for l in gzip.open(f, "rt", encoding="utf-8"):
            j = json.loads(l)
            if j["id"] in widziane or j["judgmentType"] not in TYP or len(j.get("textContent", "")) < 400:
                continue
            pula[TYP[j["judgmentType"]]].append({
                "saos_id": j["id"], "zrodlo": f"https://www.saos.org.pl/judgments/{j['id']}",
                "sygnatura": j["courtCases"][0]["caseNumber"], "data": j["judgmentDate"],
                "rodzaj_saos": TYP[j["judgmentType"]], "state": fragment(j["textContent"])})
    rng = random.Random(2025)
    dev, train = [], []
    for rodzaj, rows in pula.items():
        rng.shuffle(rows)
        dev += rows[:DEV_NA_RODZAJ]
        train += rows[DEV_NA_RODZAJ:]
    q = {"rodzaj": questions("sad")["rodzaj"]}
    with (ROOT / "data" / "bench" / "sad_real_dev.jsonl").open("w") as f:
        for i, r in enumerate(dev):
            f.write(json.dumps({"id": f"sad_real_dev-{i:03d}", "domena": "sad_real", "zrodlo": r["zrodlo"],
                                "state": r["state"], "questions": q, "expected": {"rodzaj": r["rodzaj_saos"]},
                                "przejrzane": True}, ensure_ascii=False) + "\n")
    with (ROOT / "data" / "real" / "saos_2025_train.jsonl").open("w") as f:
        for r in train:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"dev {len(dev)}; pula treningowa: " + ", ".join(f"{k} {sum(r['rodzaj_saos'] == k for r in train)}" for k in pula))


if __name__ == "__main__":
    main()
