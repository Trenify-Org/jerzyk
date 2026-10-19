"""Re-score stored predictions after reference labels were corrected, without running the models again.

  python -m scripts.rescore_results --suffix relabel jerzyk-v4-kal-real2 bielik-11b-real2 …
  → results/bench-<name>-relabel.json, scored against the current labels in data/bench/*_test.jsonl

Every results file keeps each prediction (`details`: id, question, prediction, confidence), so accuracy, Brier score,
±1 accuracy and ECE can be recomputed for new labels. The MAE of scores needs the full probability distribution,
which is not stored, so it is left out. Latency figures are copied from the original run.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

from scripts.evaluate import ece
from scripts.results_table import normalise_file

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
BENCH = ROOT / "data" / "bench"


def domain_of(doc_id):
    """Domain of a document from its id: "adm_real-008" → adm_real, "sad-test-003" → sad."""
    return doc_id.split("-")[0]


def load_gold(folder=BENCH):
    """Current reference answers and question types from the benchmark files."""
    gold, types = {}, {}
    for f in sorted(Path(folder).glob("*_test.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            for qid, q in row["questions"].items():
                gold[(row["id"], qid)] = row["expected"][qid]
                types[qid] = q["type"]
    return gold, types


def _metrics(items, qtype):
    m = {"accuracy": round(mean(d["pred"] == d["gold"] for d in items), 3), "n": len(items)}
    if qtype == "noul":
        p_true = [d["conf"] if d["pred"] is True else 1 - d["conf"] for d in items]
        m["brier"] = round(mean((p - (d["gold"] is True)) ** 2 for p, d in zip(p_true, items)), 3)
    if qtype == "score":
        m["accuracy_pm1"] = round(mean(abs(int(d["pred"]) - int(d["gold"])) <= 1 for d in items), 3)
    return m


def rescore(details, gold, types):
    """New `result` fields for stored `details` scored against `gold` {(id, question): answer}."""
    new_details = [{**d, "gold": gold.get((d["id"], d["q"]), d["gold"])} for d in details]
    groups = defaultdict(list)
    for d in new_details:
        groups[(domain_of(d["id"]), d["q"])].append(d)
    questions = {f"{dom}.{q}": _metrics(items, types.get(q, "choice")) for (dom, q), items in sorted(groups.items())}
    domains = sorted({dom for dom, _ in groups})
    per_domain = [mean(m["accuracy"] for k, m in questions.items() if k.split(".")[0] == dom) for dom in domains]
    return {
        "questions": questions,
        "mean_accuracy_over_domains": round(mean(per_domain), 3),
        "ece": round(ece([(d["conf"], d["pred"] == d["gold"]) for d in new_details]), 3),
        "details": new_details,
    }


def rescore_file(name, suffix, gold, types):
    data = normalise_file(json.loads((RESULTS / f"bench-{name}.json").read_text(encoding="utf-8")))
    new = rescore(data["details"], gold, types)
    changed = sum(a["gold"] != b["gold"] for a, b in zip(data["details"], new["details"]))
    result = {**data["result"], "model": f"{data['result'].get('model', name)}-{suffix}",
              "questions": new["questions"], "mean_accuracy_over_domains": new["mean_accuracy_over_domains"],
              "ece": new["ece"], "rescored_from": name}
    out = RESULTS / f"bench-{name}-{suffix}.json"
    out.write_text(json.dumps({"result": result, "details": new["details"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return out, changed, data["result"].get("mean_accuracy_over_domains"), new["mean_accuracy_over_domains"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="+", help="result names, as in results/bench-<name>.json")
    ap.add_argument("--suffix", default="relabel", help="appended to the output name")
    args = ap.parse_args()
    gold, types = load_gold()
    for name in args.names:
        out, changed, before, after = rescore_file(name, args.suffix, gold, types)
        print(f"{name}: {changed} answers re-labelled, mean {before} → {after} ({out.name})")


if __name__ == "__main__":
    main()
