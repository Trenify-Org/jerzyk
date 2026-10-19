"""Automatic check of the test set before manual review: marks letters that may not match their answer.

  python -m scripts.check_benchmark --url http://127.0.0.1:9934     # adds the "flags" field to data/bench/*_{test,dev}.jsonl

Checks:
- rules: does the letter contain a deadline when the answer says "deadline: yes" (and vice versa), does the length
  of the deadline match the urgency, is there a date in the letter, is the text not too short or cut off,
- Bielik: does its reading of the type (for e-mails: the department) agree with the reference answer.
A letter with a flag goes to review first (review_benchmark.py --flags).
"""
import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from jerzyk import deadlines
from scripts.generate_training_data import check_with_bielik
from scripts.llm import letter_probs

BENCH = Path(__file__).resolve().parent.parent / "data" / "bench"
DAYS = re.compile(r"(\d{1,3}|siedmiu|czternastu|tygodnia|dwóch tygodni|trzydziestu|dwudziestu jeden)\s*(dni|tygodni)?", re.I)
WORD_NUMBERS = {"siedmiu": 7, "tygodnia": 7, "czternastu": 14, "dwóch tygodni": 14, "dwudziestu jeden": 21, "trzydziestu": 30}


def deadline_length(text):
    """Shortest deadline in days written in the letter as "within N days / of a week …" (or None)."""
    results = []
    for m in re.finditer(r"(?:w\s+(?:nieprzekraczalnym\s+)?terminie|w\s+ciągu)\s+(\d{1,3}|siedmiu|czternastu|tygodnia|"
                         r"dwóch\s+tygodni|dwudziestu\s+jeden|trzydziestu)(?:\s+dni)?", text, re.I):
        s = re.sub(r"\s+", " ", m.group(1).lower())
        results.append(int(s) if s.isdigit() else WORD_NUMBERS.get(s))
    return min([w for w in results if w], default=None)


def rule_flags(r):
    """Rule-based flags for one row (plus the generator's own problems)."""
    flags = list(r.get("generation_problems", []))
    t, e = r["state"], r["expected"]
    if len(t) < 150:
        flags.append("too short")
    if r["domain"] != "email":
        if not (deadlines._DATE_WORDS.search(t) or deadlines._DATE_DIGITS.search(t)):
            flags.append("no date in the letter")
        n = deadline_length(t)
        dates = [x for x in deadlines.find(t) if x.kind == "date"]
        if e["termin"] and n is None and not dates and "niezwłocznie" not in t.lower():
            flags.append("deadline=yes, but no deadline visible")
        if not e["termin"] and n is not None:
            flags.append(f"deadline=no, but the letter has a {n}-day deadline")
        if e["termin"] and n is not None:
            expected = 3 if n <= 7 else 2 if n <= 14 else 1
            if expected != e["pilnosc"]:
                flags.append(f"urgency {e['pilnosc']}, but a {n}-day deadline suggests {expected}")
    return flags


def _check_yes_no(url, r):
    """E-mails: does Bielik see resignation and upset as the reference answer does?"""
    r["flags_yes_no"] = []
    for qid in ("rezygnacja", "zdenerwowany"):
        p_yes = letter_probs(url, r["state"], r["questions"][qid]["instructions"], ["tak", "nie"])[0]
        if (p_yes >= 0.5) != r["expected"][qid]:
            r["flags_yes_no"].append(f"Bielik: {qid}={'tak' if p_yes >= 0.5 else 'nie'} ({p_yes:.2f})")
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:9934")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--recheck", action="store_true", help="check also files that were already checked")
    ap.add_argument("--files", default="*_test.jsonl,*_dev.jsonl", help="file patterns in data/bench (without *_real_*)")
    args = ap.parse_args()
    paths = sorted({p for w in args.files.split(",") for p in BENCH.glob(w) if "_real_" not in p.name})
    for path in paths:
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        if all("flags" in r for r in rows) and not args.recheck:
            continue  # file already checked (resuming after an interruption)
        with ThreadPoolExecutor(args.workers) as ex:
            list(ex.map(lambda r: check_with_bielik(args.url, r), rows))
        if path.name.startswith("email"):
            with ThreadPoolExecutor(args.workers) as ex:
                list(ex.map(lambda r: _check_yes_no(args.url, r), rows))
        for r in rows:
            r["flags"] = rule_flags(r) + r.pop("flags_yes_no", [])
            if not r.pop("consistent"):
                qid = "dzial" if r["domain"] == "email" else "rodzaj"
                r["flags"].append(f"Bielik reads {qid} as {r['bielik_reading'][qid]} ({r['bielik_reading']['p']})")
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        n = sum(bool(r["flags"]) for r in rows)
        print(f"{path.name}: {n}/{len(rows)} flagged", flush=True)


if __name__ == "__main__":
    main()
