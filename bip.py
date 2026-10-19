"""Pobiera prawdziwe obwieszczenia urzędów (samorzad.gov.pl, gov.pl) — pisma administracyjne do benchmarku.

  .venv/bin/python bip.py data/real/bip_urls.txt      # data/real/bip.jsonl

Treść jest w załączniku PDF; zapisujemy tekst + propozycję odpowiedzi z tytułu (do ręcznego przeglądu).
Obwieszczenia to dokumenty urzędowe (art. 4 pr. aut.). Nazwiska osób prywatnych trzeba zanonimizować przed publikacją.
"""
import io
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from pypdf import PdfReader

OUT = Path(__file__).parent / "data" / "real" / "bip.jsonl"
UA = {"User-Agent": "Mozilla/5.0 (jerzyk-bench; badania)"}


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def sugestia(tytul, tekst):
    """Propozycja etykiet według SPEC.md z treści pisma; zawsze do potwierdzenia przez człowieka.

    Termin z treści, nie z tytułu: także zawiadomienie o wszczęciu z „14 dni na uwagi” otwiera adresatowi termin.
    """
    m = re.search(r"w\s+terminie\s+(\d+|siedmiu|czternastu)\s+dni", tekst)
    dni = None if not m else (int(m.group(1)) if m.group(1).isdigit() else {"siedmiu": 7, "czternastu": 14}[m.group(1)])
    termin = dni is not None
    pil = 0 if not termin else 3 if dni <= 7 else 2 if dni <= 14 else 1
    t = tytul.lower()
    if any(k in t for k in ("dowod", "wypowiedzenia", "nowego terminu", "przedłużeniu", "przedluzeniu",
                            "wszczęci", "wszczeci", "wydaniu decyzji")):
        return {"rodzaj": "zawiadomienie", "termin": termin, "pilnosc": pil}
    return {"termin": termin, "pilnosc": pil}


def main():
    global OUT
    if len(sys.argv) > 2:  # opcjonalny plik wynikowy, np. data/real/bip_v2.jsonl
        OUT = Path(sys.argv[2])
    urls = [u.strip() for u in Path(sys.argv[1]).read_text().splitlines() if u.strip() and not u.startswith("#")]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    gotowe = {json.loads(l)["zrodlo"] for l in OUT.read_text().splitlines()} if OUT.exists() else set()
    with OUT.open("a") as f:
        for url in urls:
            if url in gotowe:
                continue
            try:
                html = fetch(url).decode("utf-8", "replace")
                zal = re.findall(r'href="(/attachment/[0-9a-f-]{36})"', html)
                if not zal:
                    print("brak załącznika:", url)
                    continue
                host = "https://" + url.split("/")[2]
                plik = fetch(host + zal[0])
                if plik[:2] == b"PK":  # .docx — tekst z word/document.xml
                    import zipfile
                    xml = zipfile.ZipFile(io.BytesIO(plik)).read("word/document.xml").decode("utf-8", "replace")
                    tekst = re.sub(r"<[^>]+>", " ", re.sub(r"</w:p>", "\n", xml))
                else:
                    pdf = PdfReader(io.BytesIO(plik))
                    tekst = "\n".join(p.extract_text() or "" for p in pdf.pages)
                tekst = re.sub(r"[ \t]+", " ", tekst).strip()
                if len(tekst) < 200:
                    print("pusty PDF (skan?):", url)
                    continue
                tytul = url.rstrip("/").split("/")[-1].replace("-", " ")
                f.write(json.dumps({"zrodlo": url, "tytul": tytul, "state": tekst[:8000],
                                    "sugestia": sugestia(tytul, tekst), "domena": "adm", "przejrzane": False},
                                   ensure_ascii=False) + "\n")
                f.flush()
                print("ok:", tytul[:90])
            except Exception as e:  # pojedyncze strony bywają niedostępne — idziemy dalej
                print("błąd:", url, e)
            time.sleep(1)


if __name__ == "__main__":
    main()
