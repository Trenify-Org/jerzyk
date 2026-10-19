"""Collects addresses of real official notices from many offices (samorzad.gov.pl) → data/real/bip_urls_v2.txt.

  python -m scripts.collect_notice_urls                  # then: .venv/bin/python -m scripts.fetch_notices data/real/bip_urls_v2.txt

v1 had 30 notices from four municipalities (23 from one, ~18 templates) — the result depended on a few templates.
Here: notice listings from many municipalities and districts, at most --per-office letters from one office.
Listings found with the search engine (2026-10-18); append further ones to LISTINGS.
"""
import argparse
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (jerzyk-bench; badania)"}
HOST = "https://samorzad.gov.pl"
LISTINGS = [
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
NOTICE_WORDS = re.compile(r"obwieszcz|zawiadom|decyz|postanow|wezwan|ogloszenie-o|informacja-o", re.I)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-office", type=int, default=8)
    args = parser.parse_args()
    known = set((ROOT / "data" / "real" / "bip_urls.txt").read_text().split())
    result = []
    for listing in LISTINGS:
        slug = listing.split("/")[2]
        try:
            with urllib.request.urlopen(urllib.request.Request(HOST + listing, headers=UA), timeout=60) as r:
                html = r.read().decode("utf-8", "replace")
        except Exception as e:
            print("no listing:", listing, e)
            continue
        links = []
        for href in re.findall(rf'href="(/web/{re.escape(slug)}/[^"#?]+)"', html):
            if href != listing and NOTICE_WORDS.search(href.split("/")[-1]) and HOST + href not in known and HOST + href not in links:
                links.append(HOST + href)
        result += links[:args.per_office]
        print(f"{slug}: {len(links)} letters, taking {min(len(links), args.per_office)}", flush=True)
        time.sleep(1)
    result = list(dict.fromkeys(result))
    (ROOT / "data" / "real" / "bip_urls_v2.txt").write_text("\n".join(result) + "\n")
    print(f"total {len(result)} addresses")


if __name__ == "__main__":
    main()
