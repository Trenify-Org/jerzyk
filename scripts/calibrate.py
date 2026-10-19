"""Temperature scaling on the dev set (separately for choice / noul / score) — so that "90%" means 90%.

  USE_TF=0 .venv/bin/python -m scripts.calibrate --model models/jerzyk-1.0 data/bench/*_dev.jsonl
  → models/jerzyk-1.0.calibration.json  {"choice": T, "noul": T, "score": T}

The published model folder holds the same temperatures as calibration.json.
laya-train calibrates on a slice of the training data (in-sample), so its confidence comes out inflated. Here one
temperature per question type is fitted on letters the model has not seen: p_i ∝ p_i^(1/T). T > 1 lowers confidence.
evaluate.py and jerzyk/serve.py apply the file if it exists next to the model (the old <model>.kalibracja.json too).
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts.evaluate import ask_laya

GRID = [round(0.25 + 0.05 * i, 2) for i in range(96)]  # 0.25 … 5.0


def scale(p, t):
    w = {k: max(v, 1e-9) ** (1 / t) for k, v in p.items()}
    s = sum(w.values())
    return {k: v / s for k, v in w.items()}


def calibration_file(model):
    return Path(str(model).rstrip("/") + ".calibration.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--model", required=True)
    args = ap.parse_args()
    rows = [json.loads(l) for f in args.files for l in Path(f).read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if r.get("ok", True)]
    data = defaultdict(list)  # type → [(probs, gold)]
    for r in rows:
        probs = ask_laya(args.model, r["state"], r["questions"])
        for qid, q in r["questions"].items():
            data[q["type"]].append((probs[qid], r["expected"][qid]))
    result = {}
    for typ, pairs in data.items():
        nll = lambda t: -sum(math.log(max(scale(p, t).get(g, 0), 1e-9)) for p, g in pairs) / len(pairs)
        result[typ] = min(GRID, key=nll)
        print(f"{typ}: n={len(pairs)}  T={result[typ]}  NLL {nll(1.0):.3f} → {nll(result[typ]):.3f}", flush=True)
    calibration_file(args.model).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"saved {calibration_file(args.model)}")


if __name__ == "__main__":
    main()
