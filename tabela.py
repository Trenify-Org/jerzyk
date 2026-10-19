"""Tabela wyników jerzyk-bench do README (markdown, po angielsku) z plików results/bench-*.json.

  python3 tabela.py > wydanie/wyniki.md

E-maile mają nowy test (v3, reguły SPEC 2026-10-18), więc dla modeli ocenianych wcześniej pytania e-mailowe
bierzemy z osobnego przebiegu *-email3; pozostałe dziedziny z pełnego przebiegu (te same pliki testowe).
"""
import json
from pathlib import Path
from statistics import mean

R = Path(__file__).parent / "results"
MODELE = {  # nazwa w tabeli: (pełny test, e-maile v3 albo None, prawdziwe v2)
    "**Jerzyk 1.0** (322M)": ("jerzyk-v4-kal", None, "jerzyk-v4-kal-real2"),
    "basal-2.0-mini (1.5B)": ("basal-2.0-mini", "basal-2.0-mini-email3", "basal-2.0-mini-real2"),
    "Qwen3 8B": ("qwen3-8b", "qwen3-8b-email3", "qwen3-8b-real2"),
    "Bielik 11B v3": ("bielik-11b", "bielik-11b-email3", "bielik-11b-real2"),
}
NAZWY = {"sad": "Court", "adm": "Administrative", "ksieg": "Accounting", "email": "Customer e-mail",
         "sad_real": "Court rulings (real)", "adm_real": "Admin. notices (real)"}


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


def tabela(dane, tytul):
    kolumny = list(dane)
    qs = sorted({q for p in dane.values() for q in p})
    print(f"\n**{tytul}** — accuracy (%)\n")
    print("| Question | " + " | ".join(kolumny) + " |")
    print("|---|" + "---|" * len(kolumny))
    for q in qs:
        d, n = q.split(".")
        print(f"| {NAZWY[d]}: {n} | " + " | ".join(f"{dane[k][q]['trafnosc'] * 100:.1f}" if q in dane[k] else "–" for k in kolumny) + " |")
    print("| **Mean over domains** | " + " | ".join(f"**{srednia(dane[k]) * 100:.1f}**" for k in kolumny) + " |")


def main():
    gen = {m: pytania(p, e) for m, (p, e, _) in MODELE.items()}
    real = {m: wczytaj(r)["pytania"] for m, (_, _, r) in MODELE.items()}
    tabela(gen, "Generated test set (480 documents)")
    tabela(real, "Real documents (89 court rulings + 56 administrative notices)")
    print("\n| | " + " | ".join(MODELE) + " |\n|---|" + "---|" * len(MODELE))
    print("| ECE, real documents (lower = better) | " + " | ".join(f"{wczytaj(r)['ece']:.3f}" for _, _, r in MODELE.values()) + " |")
    print("| Median latency per document (all models on the same computer) | " +
          " | ".join(f"{wczytaj(r)['ms_mediana'] / 1000:.2f} s" for _, _, r in MODELE.values()) + " |")


if __name__ == "__main__":
    main()
