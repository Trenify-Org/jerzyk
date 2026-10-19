"""Builds the release files in wydanie/ (locally, it uploads nothing).

  python3 -m scripts.build_release
  → wydanie/github/      code (jerzyk/, scripts/, tests/, docs/, pyproject.toml), README, NOTICE, CI templates
  → wydanie/hf-model/    Jerzyk 1.0 (weights + calibration) + model card
  → wydanie/hf-dataset/  jerzyk-bench (test + dev, real documents after anonymisation) + dataset card

READMEs, NOTICE and cards are written by hand in wydanie/szablony/; this script only copies and cleans the data.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from scripts import results_table

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / "wydanie"
TEMPLATES = RELEASE / "szablony"
MODEL_SOURCE = ROOT / "models" / "jerzyk-1.0"
PUBLISHED_RESULT = ROOT / "results" / "bench-jerzyk-1.0-pub-real.json"  # written by scripts/evaluate_published.sh
GITHUB_TEMPLATES = ("README.md", "NOTICE", ".gitignore", "requirements.txt", "CITATION.cff", "SECURITY.md",
                    "CHANGELOG.md")
CODE_DOCS = ("SPEC.md", "TRAINING.md")
# note under the tables while the results are not yet measured on the published dataset
ANONYMIZATION_NOTE = (
    "> **Note.** These results were measured on the benchmark text before anonymisation of the real documents "
    "(names of judges, officials and private persons replaced with placeholders such as `[SĘDZIA]` and `[OSOBA]`). "
    "On the published, anonymised text Jerzyk 1.0 scores 86.3% instead of 86.6% on real documents. "
    "The other models will be re-measured on the published text in a later update.")
# fields of a published row, in this order
FIELDS = ["id", "domain", "split", "state", "questions", "expected", "source", "author", "labels", "note"]
# benchmark files published to the dataset; real documents come from the anonymised folder
TEST_FILES = ["sad_test", "adm_test", "ksieg_test", "email_test", "sad_dev", "adm_dev", "ksieg_dev", "email_dev",
              "sad_real_test", "sad_real_fragmenty_test", "sad_real_dev", "adm_real_test"]
REAL_PREFIXES = ("adm_real", "sad_real")


def clean_folder(folder):
    """Empties the folder for a fresh build; the git history (.git) is kept."""
    if not folder.exists():
        return
    for old in folder.iterdir():
        if old.name == ".git":
            continue
        shutil.rmtree(old) if old.is_dir() else old.unlink()


def clean_row(row, generated=False):
    """Fields to publish. Fictitious numbers in generated documents could match real people or companies:
    PESEL → [PESEL], phone → [TELEFON], e-mail domain → example.pl (this does not change the model results)."""
    row = {k: row[k] for k in FIELDS if k in row}
    if generated:
        text = re.sub(r"\b\d{11}\b", "[PESEL]", row["state"])
        text = re.sub(r"(?<!\d)(?:\+48[ -]?)?\d{3}[ -]\d{3}[ -]\d{3}(?!\d)", "[TELEFON]", text)
        if re.search(r"tel", text, re.I):  # "tel" (Polish: phone) in the text: also mask 2-3-2-2 digit numbers
            text = re.sub(r"\b(\d{2}[ -]\d{3}[ -]\d{2}[ -]\d{2})\b(?=\D{0,15}$|\s)", "[TELEFON]", text)
        row["state"] = re.sub(r"([A-Za-z0-9._%+-]+)@[A-Za-z0-9.-]+\.[a-z]{2,}", r"\1@example.pl", text)
    return row


def _copy_if_exists(src, dst):
    if src.exists():
        shutil.copy2(src, dst)


def copy_code(root, github):
    """Code package, scripts (.py and .sh only), tests with fixtures, docs and pyproject.toml."""
    ignore_cache = shutil.ignore_patterns("__pycache__")
    shutil.copytree(root / "jerzyk", github / "jerzyk", ignore=ignore_cache)
    (github / "scripts").mkdir(parents=True, exist_ok=True)
    for f in (root / "scripts").iterdir():
        if f.is_file() and f.suffix in (".py", ".sh"):
            shutil.copy2(f, github / "scripts" / f.name)
    shutil.copytree(root / "tests", github / "tests", ignore=ignore_cache)
    (github / "docs").mkdir(parents=True, exist_ok=True)
    for f in CODE_DOCS:
        shutil.copy2(root / "docs" / f, github / "docs" / f)
    shutil.copy2(root / "pyproject.toml", github / "pyproject.toml")


def copy_templates(templates, github):
    """README, NOTICE, .gitignore, CI and other GitHub files from the templates."""
    for f in GITHUB_TEMPLATES:
        _copy_if_exists(templates / f"github-{f}", github / f)
    shutil.copytree(templates / "github-.github", github / ".github")


def build_model(weights, model_dir, templates):
    """Model weights and calibration with the model card (README) and NOTICE."""
    if model_dir.exists():
        shutil.rmtree(model_dir)
    shutil.copytree(weights, model_dir, ignore=shutil.ignore_patterns("checkpoint_latest"))
    _copy_if_exists(templates / "hf-model-README.md", model_dir / "README.md")
    _copy_if_exists(templates / "github-NOTICE", model_dir / "NOTICE")


def write_dataset(bench_dir, anonymised_dir, out_dir):
    """Writes the published *.jsonl files; generated rows are masked, real rows must be anonymised first."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in TEST_FILES:
        real = name.startswith(REAL_PREFIXES)
        src = (anonymised_dir if real else bench_dir) / f"{name}.jsonl"
        if not src.exists():
            raise SystemExit(f"missing anonymised file {name} — run the anonymisation first")
        rows = [clean_row(json.loads(line), generated=not real) for line in src.read_text().splitlines() if line.strip()]
        (out_dir / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        print(f"{name}: {len(rows)}")


def fill_markers(text, tables, note):
    """Puts the results tables and the anonymisation note into a README template."""
    text = text.replace("<!-- RESULTS -->", tables.strip()).replace("<!-- ANONYMIZATION_NOTE -->", note)
    return text.replace("\n\n\n", "\n\n")


def run_results_table(published):
    """Markdown tables from scripts/results_table.py (run in the repo root)."""
    cmd = [sys.executable, "-m", "scripts.results_table", *(["--published"] if published else [])]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout


def main():
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    github = RELEASE / "github"
    clean_folder(github)
    copy_code(ROOT, github)
    copy_templates(TEMPLATES, github)

    model = RELEASE / "hf-model"
    build_model(MODEL_SOURCE, model, TEMPLATES)

    dataset = RELEASE / "hf-dataset"
    write_dataset(ROOT / "data" / "bench", RELEASE / "anonimizacja", dataset / "data")
    _copy_if_exists(TEMPLATES / "hf-dataset-README.md", dataset / "README.md")
    _copy_if_exists(TEMPLATES / "github-NOTICE", dataset / "NOTICE")
    for d in (github, model, dataset):
        shutil.copy2(TEMPLATES / "LICENSE", d / "LICENSE")

    # results go in place of <!-- RESULTS -->: on the published dataset if measured, otherwise older measurements
    published = PUBLISHED_RESULT.exists()
    if not published:
        print("WARNING: no results on the published dataset yet, the tables use older measurements "
              "(scripts/evaluate_published.sh)")
    tables = run_results_table(published)
    note = "" if published else ANONYMIZATION_NOTE
    index = results_table.model_index(*results_table.jerzyk_means(published)).rstrip("\n")
    (model / "README.md").write_text((model / "README.md").read_text().replace("<!-- MODEL_INDEX -->", index))
    for readme in (github / "README.md", model / "README.md", dataset / "README.md"):
        if readme.exists():
            readme.write_text(fill_markers(readme.read_text(), tables, note))


if __name__ == "__main__":
    main()
