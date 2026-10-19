"""Downloads public legal sources to data/prawo/ (resumes where it stopped).

  python -m scripts.fetch_legal_sources saos        # SAOS rulings from --since (default 2020), data/prawo/saos-od-2020/strona-NNNNN.jsonl.gz
  python -m scripts.fetch_legal_sources eli-meta    # metadata of all Dz.U. and M.P. acts (ELI API of the Sejm), data/prawo/eli/{DU,MP}.jsonl
  python -m scripts.fetch_legal_sources eli-text    # texts of acts in force from Dz.U. (HTML, or PDF if there is no HTML), data/prawo/eli/tekst/

Rulings and normative acts are not subject to copyright (art. 4 of the Polish Copyright Act). We send one request at a time
with a pause, so as not to burden public servers. The data serves for training and the dev set of Jerzyk;
we do not publish it in full (the sources provide it themselves).
"""
import argparse
import gzip
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "prawo"
UA = {"User-Agent": "jerzyk-bench/0.1", "Accept": "application/json"}
SAOS_DUMP = "https://www.saos.org.pl/api/dump/judgments"
ELI = "https://api.sejm.gov.pl/eli"
PAUSE = 0.5


def get(url, raw=False, tries=5):
    for attempt in range(tries):
        try:
            headers = {**UA, "Accept": "*/*"} if raw else UA  # PDF/HTML with Accept: application/json → 406
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as r:
                data = r.read()
            return data if raw else json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(10 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"failed to download {url}")


def saos(args):
    folder = OUT / f"saos-od-{args.since[:4]}"  # folder name on disk: "od" = "from"
    folder.mkdir(parents=True, exist_ok=True)
    page = len(list(folder.glob("strona-*.jsonl.gz")))  # full pages already downloaded
    while True:
        response = get(f"{SAOS_DUMP}?pageSize={args.page_size}&pageNumber={page}&judgmentStartDate={args.since}")
        items = response["items"]
        if not items:
            break
        tmp = folder / f"strona-{page:05d}.tmp"
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        tmp.rename(folder / f"strona-{page:05d}.jsonl.gz")
        page += 1
        print(f"saos: page {page}, rulings ~{page * args.page_size}", flush=True)
        time.sleep(PAUSE)


def eli_meta(_args):
    folder = OUT / "eli"
    folder.mkdir(parents=True, exist_ok=True)
    for pub in ("DU", "MP"):
        path = folder / f"{pub}.jsonl"
        done = {json.loads(line)["rok"] for line in path.read_text(encoding="utf-8").splitlines()} if path.exists() else set()  # "rok": year, key already on disk
        with path.open("a", encoding="utf-8") as f:
            for year in get(f"{ELI}/acts/{pub}")["years"]:
                if year in done:
                    continue
                for item in get(f"{ELI}/acts/{pub}/{year}")["items"]:
                    f.write(json.dumps({"rok": year, **item}, ensure_ascii=False) + "\n")
                print(f"eli {pub} {year}", flush=True)
                time.sleep(PAUSE)


def eli_text(_args):
    folder = OUT / "eli" / "tekst"
    folder.mkdir(parents=True, exist_ok=True)
    acts = [json.loads(line) for line in (OUT / "eli" / "DU.jsonl").read_text(encoding="utf-8").splitlines()]
    acts = [a for a in acts if a.get("status") == "obowiązujący"]  # API status value: "in force"
    for n, act in enumerate(acts, 1):
        name = act["address"]
        if any(folder.glob(name + ".*")):
            continue
        url_path = f"{ELI}/acts/{act['publisher']}/{act['year']}/{act['pos']}"
        try:
            if act.get("textHTML"):
                data, ext = get(url_path + "/text.html", raw=True), "html"
            elif act.get("textPDF"):
                data, ext = get(url_path + "/text.pdf", raw=True), "pdf"
            else:
                continue
        except RuntimeError as e:  # a single act does not stop the whole run
            print(e, flush=True)
            continue
        if data:
            (folder / f"{name}.{ext}").write_bytes(data)
        if n % 100 == 0:
            print(f"eli text: {n}/{len(acts)}", flush=True)
        time.sleep(PAUSE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["saos", "eli-meta", "eli-text"])
    parser.add_argument("--page-size", type=int, default=100, help="saos: rulings per page")
    parser.add_argument("--since", default="2020-01-01", help="saos: rulings issued from this date (current law)")
    args = parser.parse_args()
    {"saos": saos, "eli-meta": eli_meta, "eli-text": eli_text}[args.cmd](args)


if __name__ == "__main__":
    main()
