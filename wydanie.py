"""Składa pliki do publikacji w wydanie/ (lokalnie — niczego nie wysyła).

  python3 wydanie.py
  → wydanie/github/      kod, SPEC, TRENING, demo, LICENSE, NOTICE, README
  → wydanie/hf-model/    Jerzyk 1.0 (wagi + kalibracja) + karta modelu
  → wydanie/hf-dataset/  jerzyk-bench (test + dev, prawdziwe pisma po anonimizacji) + karta zbioru

README, NOTICE i karty piszemy ręcznie w wydanie/szablony/; ten skrypt tylko kopiuje i czyści dane.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
W = ROOT / "wydanie"
KOD = ["jerzyk.py", "tasks.py", "deadlines.py", "test_deadlines.py", "test_jerzyk.py", "test_wydanie.py", "test_anonim_saos.py", "test_tabela.py", "run_wydanie_eval.sh", "gen_bench.py", "train_v1.py", "precheck.py", "review.py", "evaluate.py",
       "calibrate.py", "bench.py", "saos.py", "saos_2025.py", "prawo.py", "bip.py", "bip_zbierz.py", "bip_trening.py",
       "jerzyk_serve.py", "tabela.py", "wydanie.py", "anonim_saos.py", "eval_laya.sh", "run_v4.sh", "run_basal.sh", "SPEC.md", "TRENING.md"]
POLA = ["id", "domena", "split", "state", "questions", "expected", "zrodlo", "autor", "etykiety", "uwaga"]
TEST = ["sad_test", "adm_test", "ksieg_test", "email_test", "sad_dev", "adm_dev", "ksieg_dev", "email_dev",
        "sad_real_test", "sad_real_fragmenty_test", "sad_real_dev", "adm_real_test"]


def czysc(r, wygenerowane=False):
    """Pola do publikacji. W pismach wygenerowanych fikcyjne numery mogłyby trafić na prawdziwe osoby lub firmy:
    PESEL → [PESEL], telefon → [TELEFON], domena e-maila → example.pl (na wyniki modeli to nie wpływa)."""
    r = {k: r[k] for k in POLA if k in r}
    if wygenerowane:
        t = re.sub(r"\b\d{11}\b", "[PESEL]", r["state"])
        t = re.sub(r"(?<!\d)(?:\+48[ -]?)?\d{3}[ -]\d{3}[ -]\d{3}(?!\d)", "[TELEFON]", t)
        t = re.sub(r"\b(\d{2}[ -]\d{3}[ -]\d{2}[ -]\d{2})\b(?=\D{0,15}$|\s)", "[TELEFON]", t) if re.search(r"tel", t, re.I) else t
        r["state"] = re.sub(r"([A-Za-z0-9._%+-]+)@[A-Za-z0-9.-]+\.[a-z]{2,}", r"\1@example.pl", t)
    return r


def wyczysc(folder):
    """Składamy od zera: usuwa wszystko z folderu poza historią gita (.git)."""
    if not folder.exists():
        return
    for old in folder.iterdir():
        if old.name == ".git":
            continue
        shutil.rmtree(old) if old.is_dir() else old.unlink()


def main():
    gh = W / "github"
    wyczysc(gh)
    (gh / "demo").mkdir(parents=True, exist_ok=True)
    for f in KOD:
        shutil.copy2(ROOT / f, gh / f)
    shutil.copy2(ROOT / "demo" / "index.html", gh / "demo" / "index.html")
    for f in ("README.md", "NOTICE", ".gitignore", "requirements.txt"):
        if (W / "szablony" / f"github-{f}").exists():
            shutil.copy2(W / "szablony" / f"github-{f}", gh / f)

    model = W / "hf-model"
    if model.exists():
        shutil.rmtree(model)
    shutil.copytree(ROOT / "models" / "jerzyk-1.0", model, ignore=shutil.ignore_patterns("checkpoint_latest"))
    for f in ("README.md", "NOTICE"):
        src = W / "szablony" / ("hf-model-README.md" if f == "README.md" else "github-NOTICE")
        if src.exists():
            shutil.copy2(src, model / f)

    ds = W / "hf-dataset" / "data"
    ds.mkdir(parents=True, exist_ok=True)
    for n in TEST:
        # prawdziwe pisma tylko po anonimizacji (adm: osoby/adresy; SAOS: sędziowie, protokolanci — anonim_saos.py)
        prawdziwe = n.startswith(("adm_real", "sad_real"))
        src = W / "anonimizacja" / f"{n}.jsonl" if prawdziwe else ROOT / "data" / "bench" / f"{n}.jsonl"
        if not src.exists():
            raise SystemExit(f"brak zanonimizowanego {n} — najpierw anonimizacja")
        rows = [czysc(json.loads(l), not prawdziwe) for l in src.read_text().splitlines() if l.strip()]
        (ds / f"{n}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        print(f"{n}: {len(rows)}")
    for f, dst in (("hf-dataset-README.md", W / "hf-dataset" / "README.md"), ("github-NOTICE", W / "hf-dataset" / "NOTICE")):
        if (W / "szablony" / f).exists():
            shutil.copy2(W / "szablony" / f, dst)
    for d in (gh, model, W / "hf-dataset"):
        shutil.copy2(W / "szablony" / "LICENSE", d / "LICENSE")
    # tabela wyników z results/ w miejsce <!-- WYNIKI -->
    # wyniki na opublikowanej wersji zbioru (run_wydanie_eval.sh), jeśli już są; inaczej starsze pomiary
    pub = ["--pub"] if (ROOT / "results" / "bench-jerzyk-1.0-pub-real.json").exists() else []
    if not pub:
        print("UWAGA: brak wyników na opublikowanym zbiorze — tabele ze starszych pomiarów (run_wydanie_eval.sh)")
    wyniki = subprocess.run([sys.executable, str(ROOT / "tabela.py"), *pub], capture_output=True, text=True, check=True).stdout
    for f in (gh / "README.md", model / "README.md", W / "hf-dataset" / "README.md"):
        if f.exists():
            f.write_text(f.read_text().replace("<!-- WYNIKI -->", wyniki.strip()))


if __name__ == "__main__":
    main()
