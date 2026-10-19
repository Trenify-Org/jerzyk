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
    ap.add_argument("--sprzet", default="all models on the same computer", help="komputer, na którym mierzono czas")
    args = ap.parse_args()
    modele = MODELE_PUB if args.pub else MODELE
    gen = {m: pytania(p, e) for m, (p, e, _) in modele.items()}
    real = {m: wczytaj(r)["pytania"] for m, (_, _, r) in modele.items()}
    tabela(gen, "Generated test set (480 documents)")
    tabela(real, "Real documents (89 court rulings + 56 administrative notices)", przedzial=True)
    print("\n| | " + " | ".join(modele) + " |\n|---|" + "---|" * len(modele))
    print("| ECE, real documents (lower = better) | " + " | ".join(f"{wczytaj(r)['ece']:.3f}" for _, _, r in modele.values()) + " |")
    print(f"| Median latency per document ({args.sprzet}) | " +
          " | ".join(f"{wczytaj(r)['ms_mediana'] / 1000:.2f} s" for _, _, r in modele.values()) + " |")


if __name__ == "__main__":
    main()
