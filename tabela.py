"""Tabela wyników jerzyk-bench do README (markdown, po angielsku) z plików results/bench-*.json.

  python3 tabela.py > wydanie/wyniki.md
  python3 tabela.py --pub     # wyniki na opublikowanej (zanonimizowanej) wersji zbioru, z run_wydanie_eval.sh

E-maile mają nowy test (v3, reguły SPEC 2026-10-18), więc dla modeli ocenianych wcześniej pytania e-mailowe
bierzemy z osobnego przebiegu *-email3; pozostałe dziedziny z pełnego przebiegu (te same pliki testowe).
"""
import argparse
import json
import math
from pathlib import Path
from statistics import mean

R = Path(__file__).parent / "results"
MODELE = {  # nazwa w tabeli: (pełny test, e-maile v3 albo None, prawdziwe v2)
    "**Jerzyk 1.0** (322M)": ("jerzyk-v4-kal", None, "jerzyk-v4-kal-real2"),
    "basal-2.0-mini (1.5B)": ("basal-2.0-mini", "basal-2.0-mini-email3", "basal-2.0-mini-real2"),
    "Qwen3 8B": ("qwen3-8b", "qwen3-8b-email3", "qwen3-8b-real2"),
    "Bielik 11B v3": ("bielik-11b", "bielik-11b-email3", "bielik-11b-real2"),
}
# te same modele zmierzone na opublikowanym zbiorze (run_wydanie_eval.sh); e-maile są już w wersji v3
MODELE_PUB = {nazwa: (f"{n}-pub", None, f"{n}-pub-real") for nazwa, n in (
    ("**Jerzyk 1.0** (322M)", "jerzyk-1.0"), ("basal-2.0-mini (1.5B)", "basal-2.0-mini"),
    ("Qwen3 8B", "qwen3-8b"), ("Bielik 11B v3", "bielik-11b"))}
NAZWY = {"sad": "Court", "adm": "Administrative", "ksieg": "Accounting", "email": "Customer e-mail",
         "sad_real": "Court rulings (real)", "adm_real": "Admin. notices (real)"}


def wilson(p, n, z=1.96):
    """95% przedział Wilsona dla trafności p na n przykładach."""
    srodek = (p + z * z / (2 * n)) / (1 + z * z / n)
    pol = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, srodek - pol), min(1.0, srodek + pol)


def komorka(m, przedzial=False):
    """Trafność w %; z przedziałem 95% w nawiasie, gdy wynik ma liczbę przykładów `n`."""
    s = f"{m['trafnosc'] * 100:.1f}"
    if przedzial and "n" in m:
        lo, hi = wilson(m["trafnosc"], m["n"])
        s += f" ({lo * 100:.0f}–{hi * 100:.0f})"
    return s


def uzupelnij_n(pytania, liczby):
    """Starsze wyniki nie mają `n`: każde pismo dostaje każde pytanie swojej dziedziny, więc n = liczba pism."""
    out = {}
    for q, m in pytania.items():
        d = q.split(".")[0]
        out[q] = m if "n" in m or d not in liczby else {**m, "n": liczby[d]}
    return out


def liczba_pism(folder):
    """{domena: liczba pism} w plikach *_test.jsonl (tak jak liczy evaluate.py: bez pism oznaczonych ok=false)."""
    liczby = {}
    for f in Path(folder).glob("*_test.jsonl"):
        for l in f.read_text().splitlines():
            if l.strip() and json.loads(l).get("ok", True):
                d = json.loads(l)["domena"]
                liczby[d] = liczby.get(d, 0) + 1
    return liczby


def wczytaj(n):
    return json.loads((R / f"bench-{n}.json").read_text())["wynik"]


def pytania(pelny, email3):
    p = dict(wczytaj(pelny)["pytania"])
    if email3:
        p = {k: v for k, v in p.items() if not k.startswith("email.")} | wczytaj(email3)["pytania"]
    return p


def srednia(p):
    dom = sorted({k.split(".")[0] for k in p})
    return mean(mean(v["trafnosc"] for k, v in p.items() if k.startswith(d + ".")) for d in dom)


def model_index(gen, real):
    """Blok `model-index` do karty modelu na Hugging Face: średnia trafność Jerzyka na obu częściach testu."""
    wpisy = ((gen, "generated test set", "Mean accuracy over domains, generated documents"),
             (real, "real documents", "Mean accuracy over domains, real documents"))
    y = "model-index:\n- name: jerzyk-1.0\n  results:\n"
    for wartosc, czesc, opis in wpisy:
        y += ("  - task:\n      type: text-classification\n      name: Decision questions on Polish correspondence\n"
              f"    dataset:\n      name: jerzyk-bench ({czesc})\n      type: trenify/jerzyk-bench\n      split: test\n"
              f"    metrics:\n    - type: accuracy\n      value: {wartosc * 100:.1f}\n      name: {opis}\n")
    return y


def jerzyk_srednie(pub=False):
    """(średnia na wygenerowanych, średnia na prawdziwych) dla Jerzyka — te same liczby co w tabelach."""
    pelny, email3, real = (MODELE_PUB if pub else MODELE)["**Jerzyk 1.0** (322M)"]
    return srednia(pytania(pelny, email3)), srednia(wczytaj(real)["pytania"])


def tabela(dane, tytul, przedzial=False):
    kolumny = list(dane)
    qs = sorted({q for p in dane.values() for q in p})
    print(f"\n**{tytul}** — accuracy (%){', 95% confidence interval in brackets' if przedzial else ''}\n")
    print("| Question | " + " | ".join(kolumny) + " |")
    print("|---|" + "---|" * len(kolumny))
    for q in qs:
        d, n = q.split(".")
        print(f"| {NAZWY[d]}: {n} | " + " | ".join(komorka(dane[k][q], przedzial) if q in dane[k] else "–" for k in kolumny) + " |")
    print("| **Mean over domains** | " + " | ".join(f"**{srednia(dane[k]) * 100:.1f}**" for k in kolumny) + " |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pub", action="store_true", help="wyniki na opublikowanej wersji zbioru (run_wydanie_eval.sh)")
    ap.add_argument("--sprzet", help="komputer, na którym mierzono czas (domyślnie z results/sprzet-pub.txt albo: wszystkie modele na tym samym komputerze)")
    args = ap.parse_args()
    plik = R / "sprzet-pub.txt"
    args.sprzet = args.sprzet or (args.pub and plik.exists() and plik.read_text().strip()) or "all models on the same computer"
    modele = MODELE_PUB if args.pub else MODELE
    gen = {m: pytania(p, e) for m, (p, e, _) in modele.items()}
    liczby = liczba_pism(Path(__file__).parent / "data" / "bench")
    real = {m: uzupelnij_n(wczytaj(r)["pytania"], liczby) for m, (_, _, r) in modele.items()}
    tabela(gen, "Generated test set (480 documents)")
    tabela(real, "Real documents (89 court rulings + 56 administrative notices)", przedzial=True)
    print("\n| | " + " | ".join(modele) + " |\n|---|" + "---|" * len(modele))
    print("| ECE, real documents (lower = better) | " + " | ".join(f"{wczytaj(r)['ece']:.3f}" for _, _, r in modele.values()) + " |")
    print(f"| Median latency per document ({args.sprzet}) | " +
          " | ".join(f"{wczytaj(r)['ms_mediana'] / 1000:.2f} s" for _, _, r in modele.values()) + " |")
    print("\nModels compared: "
          "[Jerzyk 1.0](https://huggingface.co/trenify/jerzyk-1.0) (calibrated); "
          "[basal-2.0-mini](https://huggingface.co/Remek/basal-2.0-mini-MLX-8bit) (MLX 8-bit, native `/v1/systemone`); "
          "[Qwen3 8B](https://huggingface.co/Qwen/Qwen3-8B-GGUF) and "
          "[Bielik 11B v3.0 Instruct](https://huggingface.co/speakleash/Bielik-11B-v3.0-Instruct-GGUF) "
          "(GGUF Q4_K_M in llama.cpp, zero-shot, answer chosen from option log-probabilities).")


if __name__ == "__main__":
    main()
