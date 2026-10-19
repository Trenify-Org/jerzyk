"""Ocena modelu na zbiorach jerzyk-bench (format: state, questions, expected) — metryki z SPEC.md.

  python3 evaluate.py --kind llm --url http://127.0.0.1:9934 --name bielik data/bench/*_test.jsonl
  .venv/bin/python evaluate.py --kind laya --url models/jerzyk-v0 --name jerzyk-v0 data/bench/*_test.jsonl
"""
import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

from bench import letter_probs, post

ROOT = Path(__file__).parent


def opcje(q):
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


def ask_ensemble(models, state, questions):
    """Kilka modeli Laya/Jerzyk („a,b”): każdy po własnej kalibracji (<model>.kalibracja.json), potem średnia."""
    wyniki = []
    for m in models.split(","):
        out = ask_laya(m, state, questions)
        f = Path(m.rstrip("/") + ".kalibracja.json")
        temp = json.loads(f.read_text()) if f.exists() else {}
        for qid, q in questions.items():
            t = temp.get(q["type"], 1.0)
            w = {k: max(v, 1e-9) ** (1 / t) for k, v in out[qid].items()}
            out[qid] = {k: v / sum(w.values()) for k, v in w.items()}
        wyniki.append(out)
    return {qid: {k: sum(o[qid][k] for o in wyniki) / len(wyniki) for k in wyniki[0][qid]} for qid in questions}


def ece(pairs, bins=15):
    """pairs: (pewność wybranej odpowiedzi, czy trafna)."""
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
    ap.add_argument("--kalibracja", help="plik z calibrate.py ({typ: temperatura}); stosowany do odpowiedzi modelu")
    args = ap.parse_args()
    ask = {"llm": ask_llm, "systemone": ask_systemone, "laya": ask_laya, "ensemble": ask_ensemble}[args.kind]
    if args.kalibracja:
        temp, surowe = json.loads(Path(args.kalibracja).read_text()), ask

        def ask(url, state, questions):  # noqa: F811 — p_i ∝ p_i^(1/T), osobno dla typu pytania
            out = surowe(url, state, questions)
            for qid, q in questions.items():
                t = temp.get(q["type"], 1.0)
                w = {k: max(v, 1e-9) ** (1 / t) for k, v in out[qid].items()}
                out[qid] = {k: v / sum(w.values()) for k, v in w.items()}
            return out

    rows = [json.loads(l) for f in args.files for l in Path(f).read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r.get("ok", True)]  # pomijamy pisma oznaczone przy przeglądzie jako błędne
    ask(args.url, rows[0]["state"], rows[0]["questions"])  # rozgrzewka

    per_q = defaultdict(list)       # (domena, qid) -> wyniki
    calib, times, detail = [], [], []
    for n, r in enumerate(rows, 1):
        t0 = time.perf_counter()
        probs = ask(args.url, r["state"], r["questions"])
        times.append((time.perf_counter() - t0) * 1000)
        dom = r.get("domena", "?")
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
    tabela = {}
    for (dom, qid), res in sorted(per_q.items()):
        m = {"trafnosc": round(mean([x["ok"] for x in res]), 3)}
        if res[0]["type"] == "noul":
            m["brier"] = round(mean([x["brier"] for x in res]), 3)
        if res[0]["type"] == "score":
            m["trafnosc_pm1"] = round(mean([x["pm1"] for x in res]), 3)
            m["mae"] = round(mean([x["mae"] for x in res]), 2)
        tabela[f"{dom}.{qid}"] = m
    domeny = sorted({d for d, _ in per_q})
    wynik = {
        "model": args.name, "n_pism": len(rows),
        "trafnosc_srednia_dziedzin": round(mean([
            mean([mean([x["ok"] for x in per_q[(d, q)]]) for dd, q in per_q if dd == d]) for d in domeny]), 3),
        "ece": round(ece(calib), 3),
        "ms_mediana": round(sorted(times)[len(times) // 2]),
        "ms_p95": round(sorted(times)[int(len(times) * 0.95)]),
        "pytania": tabela,
    }
    print(json.dumps(wynik, ensure_ascii=False, indent=2))
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    (out / f"bench-{args.name}.json").write_text(json.dumps({"wynik": wynik, "szczegoly": detail}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
