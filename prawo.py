"""Pobiera publiczne źródła prawa do data/prawo/ (wznawia od miejsca przerwania).

  python3 prawo.py saos        # orzeczenia z SAOS od --od (domyślnie 2020), data/prawo/saos-od-2020/strona-NNNNN.jsonl.gz
  python3 prawo.py eli-meta    # metadane wszystkich aktów Dz.U. i M.P. (API ELI Sejmu), data/prawo/eli/{DU,MP}.jsonl
  python3 prawo.py eli-tekst   # teksty aktów obowiązujących z Dz.U. (HTML, a gdy go brak — PDF), data/prawo/eli/tekst/

Orzeczenia i akty normatywne nie są przedmiotem prawa autorskiego (art. 4 pr. aut.). Pobieramy po jednym
zapytaniu naraz z przerwą, żeby nie obciążać publicznych serwerów. Dane służą do treningu i zbioru dev Jerzyka;
nie publikujemy ich w całości (źródła udostępniają je same).
"""
import argparse
import gzip
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent / "data" / "prawo"
UA = {"User-Agent": "jerzyk-bench/0.1", "Accept": "application/json"}
SAOS_DUMP = "https://www.saos.org.pl/api/dump/judgments"
ELI = "https://api.sejm.gov.pl/eli"
PRZERWA = 0.5


def get(url, raw=False, proby=5):
    for i in range(proby):
        try:
            naglowki = {**UA, "Accept": "*/*"} if raw else UA  # PDF/HTML z Accept: application/json → 406
            with urllib.request.urlopen(urllib.request.Request(url, headers=naglowki), timeout=120) as r:
                data = r.read()
            return data if raw else json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(10 * (i + 1))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(10 * (i + 1))
    raise RuntimeError(f"nie udało się pobrać {url}")


def saos(args):
    d = OUT / f"saos-od-{args.od[:4]}"
    d.mkdir(parents=True, exist_ok=True)
    strona = len(list(d.glob("strona-*.jsonl.gz")))  # pełne strony już pobrane
    while True:
        res = get(f"{SAOS_DUMP}?pageSize={args.rozmiar}&pageNumber={strona}&judgmentStartDate={args.od}")
        items = res["items"]
        if not items:
            break
        tmp = d / f"strona-{strona:05d}.tmp"
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        tmp.rename(d / f"strona-{strona:05d}.jsonl.gz")
        strona += 1
        print(f"saos: strona {strona}, orzeczeń ~{strona * args.rozmiar}", flush=True)
        time.sleep(PRZERWA)


def eli_meta(_args):
    d = OUT / "eli"
    d.mkdir(parents=True, exist_ok=True)
    for pub in ("DU", "MP"):
        path = d / f"{pub}.jsonl"
        gotowe = {json.loads(l)["rok"] for l in path.read_text().splitlines()} if path.exists() else set()
        with path.open("a") as f:
            for rok in get(f"{ELI}/acts/{pub}")["years"]:
                if rok in gotowe:
                    continue
                for it in get(f"{ELI}/acts/{pub}/{rok}")["items"]:
                    f.write(json.dumps({"rok": rok, **it}, ensure_ascii=False) + "\n")
                print(f"eli {pub} {rok}", flush=True)
                time.sleep(PRZERWA)


def eli_tekst(_args):
    d = OUT / "eli" / "tekst"
    d.mkdir(parents=True, exist_ok=True)
    akty = [json.loads(l) for l in (OUT / "eli" / "DU.jsonl").read_text().splitlines()]
    akty = [a for a in akty if a.get("status") == "obowiązujący"]
    for n, a in enumerate(akty, 1):
        nazwa = a["address"]
        if any(d.glob(nazwa + ".*")):
            continue
        sciezka = f"{ELI}/acts/{a['publisher']}/{a['year']}/{a['pos']}"
        try:
            if a.get("textHTML"):
                data, ext = get(sciezka + "/text.html", raw=True), "html"
            elif a.get("textPDF"):
                data, ext = get(sciezka + "/text.pdf", raw=True), "pdf"
            else:
                continue
        except RuntimeError as e:  # pojedynczy akt nie zatrzymuje całości
            print(e, flush=True)
            continue
        if data:
            (d / f"{nazwa}.{ext}").write_bytes(data)
        if n % 100 == 0:
            print(f"eli tekst: {n}/{len(akty)}", flush=True)
        time.sleep(PRZERWA)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["saos", "eli-meta", "eli-tekst"])
    ap.add_argument("--rozmiar", type=int, default=100, help="saos: orzeczeń na stronę")
    ap.add_argument("--od", default="2020-01-01", help="saos: orzeczenia wydane od tej daty (aktualne prawo)")
    args = ap.parse_args()
    {"saos": saos, "eli-meta": eli_meta, "eli-tekst": eli_tekst}[args.cmd](args)


if __name__ == "__main__":
    main()
