"""Results table for jerzyk-bench in the README (markdown, in English) from results/bench-*.json.

  python3 -m scripts.results_table > wydanie/wyniki.md
  python3 -m scripts.results_table --published   # results on the published (anonymised) benchmark, from scripts/evaluate_published.sh

E-mails have a new test (v3, rules of SPEC 2026-10-18), so for models evaluated earlier the e-mail questions
come from a separate *-email3 run; the other domains come from the full run (same test files).

Result files are read in both schemas: the old Polish keys (wynik, pytania, trafnosc, ...) and the current
English ones (result, questions, accuracy, ...). Old keys are renamed on load.
"""
import argparse
import json
import math
from pathlib import Path
from statistics import mean

from jerzyk.labels import QUESTION_NAMES

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
DATA_BENCH = ROOT / "data" / "bench"
# real documents: stored predictions re-scored after the label check of 2026-10-19 (scripts/rescore_results.py)
MODELS = {  # name in the table: (full test, e-mails v3 or None, real documents)
    "**Jerzyk 1.0** (322M)": ("jerzyk-v4-kal", None, "jerzyk-v4-kal-real2-relabel"),
    "basal-2.0-mini (1.5B)": ("basal-2.0-mini", "basal-2.0-mini-email3", "basal-2.0-mini-real2-relabel"),
    "Qwen3 8B": ("qwen3-8b", "qwen3-8b-email3", "qwen3-8b-real2-relabel"),
    "Bielik 11B v3": ("bielik-11b", "bielik-11b-email3", "bielik-11b-real2-relabel"),
}
# the same models measured on the published benchmark (scripts/evaluate_published.sh); e-mails are already v3
MODELS_PUB = {name: (f"{n}-pub", None, f"{n}-pub-real") for name, n in (
    ("**Jerzyk 1.0** (322M)", "jerzyk-1.0"), ("basal-2.0-mini (1.5B)", "basal-2.0-mini"),
    ("Qwen3 8B", "qwen3-8b"), ("Bielik 11B v3", "bielik-11b"))}
DOMAIN_NAMES = {"sad": "Court", "adm": "Administrative", "ksieg": "Accounting", "email": "Customer e-mail",
                "sad_real": "Court rulings (real)", "adm_real": "Admin. notices (real)"}
# old (Polish) result keys -> English keys written by scripts/evaluate.py
FILE_KEYS = {"wynik": "result", "szczegoly": "details"}
RESULT_KEYS = {"n_pism": "n_documents", "trafnosc_srednia_dziedzin": "mean_accuracy_over_domains",
               "ms_mediana": "ms_median", "pytania": "questions"}
METRIC_KEYS = {"trafnosc": "accuracy", "trafnosc_pm1": "accuracy_pm1"}
DEFAULT_HARDWARE = "all models on the same computer"


def wilson(p, n, z=1.96):
    """95% Wilson interval for accuracy p on n examples."""
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - margin), min(1.0, centre + margin)


def cell(m, interval=False):
    """Accuracy in %; with the 95% interval in brackets when the result has the number of examples `n`."""
    s = f"{m['accuracy'] * 100:.1f}"
    if interval and "n" in m:
        lo, hi = wilson(m["accuracy"], m["n"])
        s += f" ({lo * 100:.0f}–{hi * 100:.0f})"
    return s


def _rename(d, mapping):
    """Copy of dict `d` with keys renamed through `mapping` (unknown keys stay)."""
    return {mapping.get(k, k): v for k, v in d.items()}


def normalise_file(data):
    """Result file in the old (Polish) or the new (English) schema -> English keys."""
    top = _rename(data, FILE_KEYS)
    result = _rename(top["result"], RESULT_KEYS)
    questions = {q: _rename(m, METRIC_KEYS) for q, m in result.get("questions", {}).items()}
    return {**top, "result": {**result, "questions": questions}}


def load_result(name):
    """The `result` part of results/bench-<name>.json, with English keys."""
    return normalise_file(json.loads((RESULTS / f"bench-{name}.json").read_text(encoding="utf-8")))["result"]


def fill_n(questions, counts):
    """Old results have no `n`: each document gets every question of its domain, so n = number of documents."""
    out = {}
    for q, m in questions.items():
        d = q.split(".")[0]
        out[q] = m if "n" in m or d not in counts else {**m, "n": counts[d]}
    return out


def document_counts(folder):
    """{domain: number of documents} in *_test.jsonl files (as evaluate.py counts: without documents marked ok=false)."""
    counts = {}
    for f in Path(folder).glob("*_test.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("ok", True):
                counts[row["domain"]] = counts.get(row["domain"], 0) + 1
    return counts


def merged_questions(full, email3):
    """Questions of the full run, with the e-mail questions taken from the e-mail v3 run when there is one."""
    questions = dict(load_result(full)["questions"])
    if email3:
        questions = {k: v for k, v in questions.items() if not k.startswith("email.")} | load_result(email3)["questions"]
    return questions


def mean_over_domains(questions):
    domains = sorted({k.split(".")[0] for k in questions})
    return mean(mean(v["accuracy"] for k, v in questions.items() if k.startswith(d + ".")) for d in domains)


def model_index(gen, real):
    """`model-index` block for the Hugging Face model card: mean accuracy of Jerzyk on both parts of the test."""
    entries = ((gen, "generated test set", "Mean accuracy over domains, generated documents"),
               (real, "real documents", "Mean accuracy over domains, real documents"))
    yaml = "model-index:\n- name: jerzyk-1.0\n  results:\n"
    for value, part, description in entries:
        yaml += ("  - task:\n      type: text-classification\n      name: Decision questions on Polish correspondence\n"
                 f"    dataset:\n      name: jerzyk-bench ({part})\n      type: trenify/jerzyk-bench\n      split: test\n"
                 f"    metrics:\n    - type: accuracy\n      value: {value * 100:.1f}\n      name: {description}\n")
    return yaml


def jerzyk_means(published=False):
    """(mean over generated, mean over real) for Jerzyk, the same numbers as in the tables."""
    full, email3, real = (MODELS_PUB if published else MODELS)["**Jerzyk 1.0** (322M)"]
    return mean_over_domains(merged_questions(full, email3)), mean_over_domains(load_result(real)["questions"])


def print_table(data, title, interval=False):
    columns = list(data)
    questions = sorted({q for p in data.values() for q in p})
    print(f"\n**{title}** — accuracy (%){', 95% confidence interval in brackets' if interval else ''}\n")
    print("| Question | " + " | ".join(columns) + " |")
    print("|---|" + "---|" * len(columns))
    for q in questions:
        d, n = q.split(".")
        print(f"| {DOMAIN_NAMES[d]}: {QUESTION_NAMES.get(n, n)} | " + " | ".join(cell(data[k][q], interval) if q in data[k] else "–" for k in columns) + " |")
    print("| **Mean over domains** | " + " | ".join(f"**{mean_over_domains(data[k]) * 100:.1f}**" for k in columns) + " |")


def read_hardware():
    """Machine name written by evaluate_published.sh (the old file name is still read as a fallback)."""
    for path in (RESULTS / "hardware-published.txt", RESULTS / "sprzet-pub.txt"):
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--published", action="store_true",
                    help="results on the published version of the benchmark (scripts/evaluate_published.sh)")
    ap.add_argument("--hardware", help="machine on which latency was measured "
                                       "(default: results/hardware-published.txt, otherwise: all models on the same computer)")
    args = ap.parse_args()
    args.hardware = args.hardware or (args.published and read_hardware()) or DEFAULT_HARDWARE
    models = MODELS_PUB if args.published else MODELS
    gen = {m: merged_questions(p, e) for m, (p, e, _) in models.items()}
    counts = document_counts(DATA_BENCH)
    real = {m: fill_n(load_result(r)["questions"], counts) for m, (_, _, r) in models.items()}
    print_table(gen, "Generated test set (480 documents)")
    print_table(real, "Real documents (89 court rulings + 56 administrative notices)", interval=True)
    print("\n| | " + " | ".join(models) + " |\n|---|" + "---|" * len(models))
    print("| ECE, real documents (lower = better) | " +
          " | ".join(f"{load_result(r)['ece']:.3f}" for _, _, r in models.values()) + " |")
    print(f"| Median latency per document ({args.hardware}) | " +
          " | ".join(f"{load_result(r)['ms_median'] / 1000:.2f} s" for _, _, r in models.values()) + " |")
    print("\nModels compared: "
          "[Jerzyk 1.0](https://huggingface.co/trenify/jerzyk-1.0) (calibrated); "
          "[basal-2.0-mini](https://huggingface.co/Remek/basal-2.0-mini-MLX-8bit) (MLX 8-bit, native `/v1/systemone`); "
          "[Qwen3 8B](https://huggingface.co/Qwen/Qwen3-8B-GGUF) and "
          "[Bielik 11B v3.0 Instruct](https://huggingface.co/speakleash/Bielik-11B-v3.0-Instruct-GGUF) "
          "(GGUF Q4_K_M in llama.cpp, zero-shot, answer chosen from option log-probabilities). "
          "*Mean over domains* averages the questions of each domain first, then the domains, "
          "so every domain counts equally.")


if __name__ == "__main__":
    main()
