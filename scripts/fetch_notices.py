"""Downloads real public notices (samorzad.gov.pl, gov.pl) — administrative letters for the benchmark.

  .venv/bin/python -m scripts.fetch_notices data/real/bip_urls.txt      # data/real/bip.jsonl

The text is in a PDF attachment; we save the text + a suggested answer from the title (for manual review).
Notices are official documents (art. 4 of the Polish Copyright Act). Names of private persons must be anonymised before publication.
"""
import argparse
import io
import json
import re
import time
import urllib.request
from pathlib import Path

from pypdf import PdfReader

OUT = Path(__file__).resolve().parent.parent / "data" / "real" / "bip.jsonl"
UA = {"User-Agent": "Mozilla/5.0 (jerzyk-bench; badania)"}


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def suggestion(title, text):
    """Label suggestion according to SPEC.md from the letter's text; always to be confirmed by a human.

    The deadline comes from the text, not the title: a notice of initiation with „14 dni na uwagi” also opens a deadline for the addressee.
    """
    m = re.search(r"w\s+terminie\s+(\d+|siedmiu|czternastu)\s+dni", text)
    days = None if not m else (int(m.group(1)) if m.group(1).isdigit() else {"siedmiu": 7, "czternastu": 14}[m.group(1)])
    deadline = days is not None
    urgency = 0 if not deadline else 3 if days <= 7 else 2 if days <= 14 else 1
    lowered = title.lower()
    if any(k in lowered for k in ("dowod", "wypowiedzenia", "nowego terminu", "przedłużeniu", "przedluzeniu",
                                  "wszczęci", "wszczeci", "wydaniu decyzji")):
        return {"rodzaj": "zawiadomienie", "termin": deadline, "pilnosc": urgency}
    return {"termin": deadline, "pilnosc": urgency}


def extract_text(payload):
    if payload[:2] == b"PK":  # .docx — text from word/document.xml
        import zipfile
        xml = zipfile.ZipFile(io.BytesIO(payload)).read("word/document.xml").decode("utf-8", "replace")
        return re.sub(r"<[^>]+>", " ", re.sub(r"</w:p>", "\n", xml))
    pdf = PdfReader(io.BytesIO(payload))
    return "\n".join(p.extract_text() or "" for p in pdf.pages)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", type=Path, help="text file with one notice URL per line")
    ap.add_argument("out", type=Path, nargs="?", default=OUT, help=f"output JSONL (default: {OUT})")
    args = ap.parse_args()
    out = args.out
    urls = [u.strip() for u in args.urls.read_text(encoding="utf-8").splitlines() if u.strip() and not u.startswith("#")]
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(line)["source"] for line in out.read_text(encoding="utf-8").splitlines()} if out.exists() else set()
    with out.open("a", encoding="utf-8") as f:
        for url in urls:
            if url in done:
                continue
            try:
                html = fetch(url).decode("utf-8", "replace")
                attachments = re.findall(r'href="(/attachment/[0-9a-f-]{36})"', html)
                if not attachments:
                    print("no attachment:", url)
                    continue
                host = "https://" + url.split("/")[2]
                text = extract_text(fetch(host + attachments[0]))
                text = re.sub(r"[ \t]+", " ", text).strip()
                if len(text) < 200:
                    print("empty PDF (scan?):", url)
                    continue
                title = url.rstrip("/").split("/")[-1].replace("-", " ")
                f.write(json.dumps({"source": url, "title": title, "state": text[:8000],
                                    "suggestion": suggestion(title, text), "domain": "adm", "reviewed": False},
                                   ensure_ascii=False) + "\n")
                f.flush()
                print("ok:", title[:90])
            except Exception as e:  # some pages are sometimes unavailable — move on
                print("error:", url, e)
            time.sleep(1)


if __name__ == "__main__":
    main()
