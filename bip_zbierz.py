"""Zbiera adresy prawdziwych pism urzędowych z wielu urzędów (samorzad.gov.pl) → data/real/bip_urls_v2.txt.

  python3 bip_zbierz.py                                 # potem: .venv/bin/python bip.py data/real/bip_urls_v2.txt

v1 miał 30 obwieszczeń z czterech gmin (23 z jednej, ~18 szablonów) — wynik zależał od kilku szablonów.
Tu: listy obwieszczeń z wielu gmin i powiatów, najwyżej --na-urzad pism z jednego urzędu.
Listy znalezione wyszukiwarką (2026-10-18); dopisuj kolejne do LISTY.
"""
import argparse
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
UA = {"User-Agent": "Mozilla/5.0 (jerzyk-bench; badania)"}
HOST = "https://samorzad.gov.pl"
LISTY = [
    "/web/gmina-dobron/obwieszczenia-informacje-zawiadomienia",
    "/web/gmina-wisniew/ogloszenia-2026",
    "/web/gmina-skape/obwieszczenia-2026",
    "/web/gmina-lutomiersk/obwieszczenia-ogloszenia-zp",
    "/web/gmina-lutomiersk/warunki-zabudowy-i-zagospodarowania-przestrzennego",
    "/web/gmina-bobowa/ogloszenia-i-obwieszczenia",
    "/web/gmina-kalwaria-zebrzydowska/planowanie-przestrzenne-obwieszczenia",
    "/web/gmina-wierzbica/planowanie-przestrzenne1",
    "/web/gmina-luzino/zagospodarowanie-przestrzenne",
    "/web/miasto-i-gmina-kaczory/decyzje-o-srodowiskowych-uwarunkowaniach",
    "/web/gmina-olszanka/obwieszczenia-wojta-gminy-olszanka",
    "/web/gmina-olszanka/decyzje-srodowiskowe",
    "/web/gmina-jaslo/obwieszczenia",
    "/web/gmina-augustow/obwieszczenia",
    "/web/gmina-konstantynow-lodzki/obwieszczenia",
    "/web/powiat-swiebodzinski/obwieszczenia",
    "/web/powiat-lipski/obwieszczenia",
    "/web/gmina-somianka/obwieszczenia",
    "/web/gmina-korczew/obwieszczenia",
    "/web/gmina-ruda-maleniecka/obwieszczenia",
    "/web/gmina-janowiec-wielkopolski/obwieszczenia",
    "/web/gmina-bransk/obwieszczenia",
    "/web/gmina-skorzec/obwieszczenia",
    "/web/gmina-lubenia/obwieszczenia",
    "/web/miasto-i-gmina-lipsko/obwieszczenia",
]
SLOWA = re.compile(r"obwieszcz|zawiadom|decyz|postanow|wezwan|ogloszenie-o|informacja-o", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--na-urzad", type=int, default=8)
    args = ap.parse_args()
    stare = set((ROOT / "data" / "real" / "bip_urls.txt").read_text().split())
    wynik = []
    for lista in LISTY:
        slug = lista.split("/")[2]
        try:
            with urllib.request.urlopen(urllib.request.Request(HOST + lista, headers=UA), timeout=60) as r:
                html = r.read().decode("utf-8", "replace")
        except Exception as e:
            print("brak listy:", lista, e)
            continue
        linki = []
        for href in re.findall(rf'href="(/web/{re.escape(slug)}/[^"#?]+)"', html):
            if href != lista and SLOWA.search(href.split("/")[-1]) and HOST + href not in stare and HOST + href not in linki:
                linki.append(HOST + href)
        wynik += linki[:args.na_urzad]
        print(f"{slug}: {len(linki)} pism, biorę {min(len(linki), args.na_urzad)}", flush=True)
        time.sleep(1)
    wynik = list(dict.fromkeys(wynik))
    (ROOT / "data" / "real" / "bip_urls_v2.txt").write_text("\n".join(wynik) + "\n")
    print(f"razem {len(wynik)} adresów")


if __name__ == "__main__":
    main()
