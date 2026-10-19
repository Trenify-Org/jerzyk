"""Terminal review of test letters: letter + reference answer → you agree or not.

  python -m scripts.review_benchmark                 # 30 random unreviewed letters from all domains
  python -m scripts.review_benchmark --domain adm --count 10
  python -m scripts.review_benchmark --flags         # flagged letters from check_benchmark.py first

Keys: Enter = answer correct · n = wrong (enter a note) · s = skip · q = quit.
Each result is saved at once to data/bench/*_test.jsonl (fields reviewed, ok, note).
"""
import argparse
import json
import random
import textwrap
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "data" / "bench"


def load(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def save(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain")
    ap.add_argument("--count", type=int, default=30)
    ap.add_argument("--flags", action="store_true", help="flagged letters from check_benchmark.py first")
    args = ap.parse_args()

    paths = sorted(BENCH.glob(f"{args.domain or '*'}_test.jsonl"))
    data = {p: load(p) for p in paths}
    queue = [(p, i) for p, rows in data.items() for i, r in enumerate(rows) if not r.get("reviewed")]
    random.Random().shuffle(queue)
    if args.flags:  # flagged letters first
        queue.sort(key=lambda pi: not data[pi[0]][pi[1]].get("flags"))
    queue = queue[:args.count]

    for n, (p, i) in enumerate(queue, 1):
        r = data[p][i]
        print("\n" + "=" * 80)
        print(f"[{n}/{len(queue)}] {r['id']}\n")
        for line in r["state"].splitlines():
            print(textwrap.fill(line, 80) if line.strip() else "")
        print("\n--- reference answer ---")
        for k, v in r["expected"].items():
            if k == "pilnosc":
                v = f"{v} – {r['questions']['pilnosc']['criteria'][v]}"
            print(f"  {k}: {v}")
        if r.get("flags"):
            print("\n--- automatic check notes ---")
            for fl in r["flags"]:
                print(f"  ! {fl}")
        answer = input("\n[Enter] OK · [n] wrong · [s] skip · [q] quit > ").strip().lower()
        if answer == "q":
            break
        if answer == "s":
            continue
        r["reviewed"] = True
        r["ok"] = answer != "n"
        if not r["ok"]:
            r["note"] = input("What is wrong? > ").strip()
        save(p, data[p])

    reviewed = [r for rows in data.values() for r in rows if r.get("reviewed")]
    wrong = [r for r in reviewed if not r.get("ok")]
    print(f"\nReviewed: {len(reviewed)}, wrong: {len(wrong)}")


if __name__ == "__main__":
    main()
