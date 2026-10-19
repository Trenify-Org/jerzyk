"""Evaluates a model on jerzyk-bench sets (format: state, questions, expected) — metrics from SPEC.md.

  python -m scripts.evaluate --kind llm --url http://127.0.0.1:9934 --name bielik data/bench/*_test.jsonl
  .venv/bin/python -m scripts.evaluate --kind laya --url models/jerzyk-1.0 --name jerzyk-1.0 data/bench/*_test.jsonl
  .venv/bin/python -m scripts.evaluate --kind laya --url models/jerzyk-1.0 --calibration models/jerzyk-1.0.calibration.json data/bench/*_test.jsonl

Results go to results/bench-<name>.json: {"result": {...}, "details": [...]}.
"""
import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

from scripts.llm import letter_probs, post

ROOT = Path(__file__).resolve().parent.parent
CALIBRATION_SUFFIXES = (".calibration.json", ".kalibracja.json")  # the second one: name used before 1.0


def options_of(q):
    c = q.get("criteria")
    if q["type"] == "noul":
        return [True, False]
    return list(c) if isinstance(c, dict) else list(range(len(c)))


def ask_llm(url, state, questions):
    out = {}
    for qid, q in questions.items():
        if q["type"] == "noul":
            p = letter_probs(url, state, q["instructions"], ["tak", "nie"])
            out[qid] = {True: p[0], False: p[1]}
        elif q["type"] == "choice":
            labels = [f"{k} – {v}" if v else k for k, v in q["criteria"].items()]
            out[qid] = dict(zip(q["criteria"], letter_probs(url, state, q["instructions"], labels)))
        else:
            out[qid] = dict(enumerate(letter_probs(url, state, q["instructions"], q["criteria"])))
    return out


def _from_answers(ans, questions):
    out = {}
    for qid, q in questions.items():
        a = ans[qid]
        if q["type"] == "noul":
            out[qid] = {True: a["noul"], False: 1 - a["noul"]}
        elif q["type"] == "choice":
            out[qid] = a["probabilities"]
        else:
            out[qid] = {int(k): v for k, v in a["probabilities"].items()}
    return out


def ask_systemone(url, state, questions):
    return _from_answers(post(url + "/v1/systemone", {"state": state, "questions": questions})["answers"], questions)


_laya = {}


def ask_laya(model, state, questions):
    if model not in _laya:
        import laya
        _laya[model] = laya.load(model)
    return _from_answers(_laya[model].predict(state, questions)["answers"], questions)


def load_temperatures(model):
    """Temperatures {question type: T} of a model: <model>.calibration.json, else the old <model>.kalibracja.json, else {}."""
    for suffix in CALIBRATION_SUFFIXES:
        f = Path(str(model).rstrip("/") + suffix)
        if f.exists():
            return json.loads(f.read_text())
    return {}


def apply_temperatures(probs, questions, temperatures):
    """p_i ∝ p_i^(1/T), with T chosen per question type (1.0 when the type has no temperature)."""
    result = {}
    for qid, q in questions.items():
        t = temperatures.get(q["type"], 1.0)
        w = {k: max(v, 1e-9) ** (1 / t) for k, v in probs[qid].items()}
        total = sum(w.values())
        result[qid] = {k: v / total for k, v in w.items()}
    return result


def ask_ensemble(models, state, questions):
    """Several Laya/Jerzyk models ("a,b"): each with its own calibration, then averaged."""
    outputs = []
    for m in models.split(","):
        out = apply_temperatures(ask_laya(m, state, questions), questions, load_temperatures(m))
        outputs.append(out)
    return {qid: {k: sum(o[qid][k] for o in outputs) / len(outputs) for k in outputs[0][qid]} for qid in questions}


def ece(pairs, bins=15):
    """pairs: (confidence of the chosen answer, whether it was correct)."""
    total, err = len(pairs), 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [(c, ok) for c, ok in pairs if lo < c <= hi or (b == 0 and c == 0)]
        if sel:
            err += len(sel) / total * abs(sum(c for c, _ in sel) / len(sel) - sum(ok for _, ok in sel) / len(sel))
    return err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--kind", choices=["llm", "systemone", "laya", "ensemble"], required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--calibration", help="file from calibrate.py ({question type: temperature}); applied to the model's answers")
    args = ap.parse_args()
    ask = {"llm": ask_llm, "systemone": ask_systemone, "laya": ask_laya, "ensemble": ask_ensemble}[args.kind]
    if args.calibration:
        temperatures, raw_ask = json.loads(Path(args.calibration).read_text()), ask

        def ask(url, state, questions):  # noqa: F811 — p_i ∝ p_i^(1/T), separately per question type
            return apply_temperatures(raw_ask(url, state, questions), questions, temperatures)

    rows = [json.loads(l) for f in args.files for l in Path(f).read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r.get("ok", True)]  # skip letters marked as wrong during review
    ask(args.url, rows[0]["state"], rows[0]["questions"])  # warm-up

    per_q = defaultdict(list)       # (domain, qid) -> results
    calib, times, detail = [], [], []
    for n, r in enumerate(rows, 1):
        t0 = time.perf_counter()
        probs = ask(args.url, r["state"], r["questions"])
        times.append((time.perf_counter() - t0) * 1000)
        dom = r.get("domain", "?")
        for qid, q in r["questions"].items():
            p, gold = probs[qid], r["expected"][qid]
            pred = max(p, key=p.get)
            res = {"ok": pred == gold, "conf": p[pred], "type": q["type"]}
            if q["type"] == "noul":
                res["brier"] = (p[True] - gold) ** 2
            if q["type"] == "score":
                exp = sum(k * v for k, v in p.items())
                res.update(pm1=abs(pred - gold) <= 1, mae=abs(exp - gold))
            per_q[(dom, qid)].append(res)
            calib.append((p[pred], pred == gold))
            detail.append({"id": r.get("id"), "q": qid, "gold": gold, "pred": pred, "conf": round(p[pred], 3)})
        if n % 50 == 0:
            print(f"{n}/{len(rows)}", flush=True)

    mean = lambda xs: sum(xs) / len(xs)
    questions_table = {}
    for (dom, qid), res in sorted(per_q.items()):
        m = {"accuracy": round(mean([x["ok"] for x in res]), 3), "n": len(res)}
        if res[0]["type"] == "noul":
            m["brier"] = round(mean([x["brier"] for x in res]), 3)
        if res[0]["type"] == "score":
            m["accuracy_pm1"] = round(mean([x["pm1"] for x in res]), 3)
            m["mae"] = round(mean([x["mae"] for x in res]), 2)
        questions_table[f"{dom}.{qid}"] = m
    domains = sorted({d for d, _ in per_q})
    result = {
        "model": args.name, "n_documents": len(rows),
        "mean_accuracy_over_domains": round(mean([
            mean([mean([x["ok"] for x in per_q[(d, q)]]) for dd, q in per_q if dd == d]) for d in domains]), 3),
        "ece": round(ece(calib), 3),
        "ms_median": round(sorted(times)[len(times) // 2]),
        "ms_p95": round(sorted(times)[int(len(times) * 0.95)]),
        "questions": questions_table,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    (out / f"bench-{args.name}.json").write_text(json.dumps({"result": result, "details": detail}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
