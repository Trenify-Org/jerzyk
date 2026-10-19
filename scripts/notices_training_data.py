"""Real official letters for TRAINING v4 — from offices not in the test set (data/bench/adm_real_test.jsonl).

  python -m scripts.notices_training_data urls      # searches office sites → data/real/bip_urls_train.txt
  .venv/bin/python -m scripts.fetch_notices data/real/bip_urls_train.txt data/real/bip_train.jsonl
  python -m scripts.notices_training_data labels    # rules → data/real/bip_train_etykiety.jsonl (for generate_training_data build)

Labels from rules (as with SAOS: only what is certain):
- deadline/urgency: „w terminie N dni” (also spelled out) in a sentence about the party's action (comments, familiarising, appeal,
  complaint, requests, objection). The fiction of service („uważa się za dokonane po upływie 14 dni”) is not a deadline (SPEC.md).
  No such sentence and no „do dnia …” → deadline NO, urgency 0. Ambiguous (a date „do dnia”) → we skip the question.
- type (rodzaj): from the title — notice/notification of initiation/meeting/issue/extension → zawiadomienie;
  hunting, consultations of general plans → we skip the type question (in the test they are "inne", few examples).
"""
import argparse
import json
import re
import time
import urllib.request
from collections import Counter, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (jerzyk-bench; badania)"}
HOST = "https://samorzad.gov.pl"
# Start pages of offices outside the test set (found with the search engine 2026-10-18).
START = [
    "/web/gmina-kobior/obwieszczenia", "/web/gmina-skorzec/ogloszenia3", "/web/gmina-pokrzywnica",
    "/web/gmina-zabrodzie/ogloszenia-i-komunikaty", "/web/gmina-branszczyk/obwieszczenia",
    "/web/powiat-losicki/decyzje-o-zezwoleniu-na-realizacje-inwestycji-drogowej",
    "/web/powiat-olesnicki/obwieszczenia-dot-zrid---2024-rok", "/web/gmina-jaslo/obwieszczenia-zawiadomienia",
    "/web/gmina-lutomiersk/warunki-zabudowy-i-zagospodarowania-przestrzennego", "/web/gmina-lutomiersk/obwieszczenia-ogloszenia-zp",
    "/web/gmina-rojewo", "/web/gmina-siepraw", "/web/powiat-zambrowski", "/web/powiat-sokolowski", "/web/powiat-ostrowiecki",
    "/web/powiat-nowomiejski", "/web/gmina-bobowa/ogloszenia-i-obwieszczenia", "/web/gmina-luzino/zagospodarowanie-przestrzenne",
    "/web/gmina-lubenia", "/web/gmina-skorzec", "/web/powiat-swiebodzinski", "/web/powiat-lipski", "/web/gmina-zabrodzie",
]
LETTER = re.compile(r"obwieszcz|zawiadom|decyzj|postanowien|wszczeci|zebrani|przedluzeni", re.I)
LISTING = re.compile(r"obwieszczenia|ogloszenia|zawiadomienia|komunikaty|warunki-zabudowy|zagospodarowanie|planowanie|decyzje|rok-20|20\d\d$", re.I)
PER_OFFICE, PAGES_PER_OFFICE = 30, 25


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def collect_urls():
    test = {json.loads(line)["source"].split("/")[4] for line in (ROOT / "data/bench/adm_real_test.jsonl").read_text(encoding="utf-8").splitlines()}
    known = set((ROOT / "data/real/bip_urls.txt").read_text(encoding="utf-8").split()) | set((ROOT / "data/real/bip_urls_v2.txt").read_text(encoding="utf-8").split())
    result = []
    for start in START:
        slug = start.split("/")[2]
        if slug in test:
            continue
        queue, visited, documents = deque([start]), set(), []
        while queue and len(visited) < PAGES_PER_OFFICE and len(documents) < PER_OFFICE:
            page = queue.popleft()
            if page in visited:
                continue
            visited.add(page)
            try:
                html = get(HOST + page)
            except Exception:
                continue
            for href in re.findall(rf'href="(/web/{re.escape(slug)}/[^"#?]+)"', html):
                last = href.rstrip("/").split("/")[-1]
                url = HOST + href
                if LETTER.search(last) and len(last) > 25 and url not in known and url not in documents:
                    documents.append(url)
                elif LISTING.search(last) and href not in visited:
                    queue.append(href)
            time.sleep(0.7)
        result += [u for u in documents[:PER_OFFICE] if u not in result]
        print(f"{slug}: {len(documents[:PER_OFFICE])}", flush=True)
    (ROOT / "data/real/bip_urls_train.txt").write_text("\n".join(result) + "\n", encoding="utf-8")
    print(f"total {len(result)}")


WORD_NUMBERS = {"trzech": 3, "siedmiu": 7, "czternastu": 14, "dwudziestu jeden": 21, "trzydziestu": 30, "tygodnia": 7}
_N = r"(\d{1,3}|trzech|siedmiu|czternastu|dwudziestu\s+jeden|trzydziestu|tygodnia)\s*(?:\(\w+\)\s*)?dni"
DEADLINE = re.compile(rf"(?:(?:w\s+(?:nieprzekraczalnym\s+)?terminie|\btermin|w\s+ciągu)\s+(?:nie\s+krótszym\s+niż\s+)?{_N}"
                      rf"|{_N}\s+od\s+(?:dnia|daty))", re.I)
ACTION = re.compile(r"uwag|zapozna|odwołan|zażaleni|wniosk|sprzeciw|wypowiedz|skarg|zastrzeże|ponagleni", re.I)
FICTION = re.compile(r"uważa\s+się\s+za\s+dokonane|uznaje\s+się\s+za\s+doręczon|doręczenie\s+uważa", re.I)


def rule_labels(row):
    t = re.sub(r"\s+", " ", row["state"])
    days = []
    for m in DEADLINE.finditer(t):
        sentence = t[max(0, m.start() - 500): m.end() + 150]
        if ACTION.search(sentence) and not FICTION.search(t[max(0, m.start() - 80): m.end() + 40]):
            g = re.sub(r"\s+", " ", (m.group(1) or m.group(2)).lower())
            days.append(int(g) if g.isdigit() else WORD_NUMBERS[g])
    labels = {}
    title = row["title"].lower()
    if re.search(r"polowa|konsultac|przystapieniu do sporzadzania|plan ogolny", title):
        return None  # few examples, "other" in the test — we do not learn from rules
    if re.search(r"obwieszcz|zawiadom", title) and re.search(r"wszczeci|zebrani|wydaniu|wydanej|przedluzeni|zakonczeni|"
                                                             r"zawieszeni|podjeci|przekazaniu|ogledzin|decyzj|postanowien", title):
        labels["rodzaj"] = "zawiadomienie"
    if days:
        n = min(days)
        labels["termin"], labels["pilnosc"] = True, 3 if n <= 7 else 2 if n <= 14 else 1
    elif not re.search(r"do\s+dnia\s+\d|niezwłocznie", t, re.I):
        labels["termin"], labels["pilnosc"] = False, 0
    return labels or None


def make_labels():
    rows = [json.loads(line) for line in (ROOT / "data/real/bip_train.jsonl").read_text(encoding="utf-8").splitlines()]
    out = []
    for row in rows:
        labels = rule_labels(row)
        if labels:
            out.append({"source": row["source"], "state": row["state"], "expected": labels})
    (ROOT / "data/real/bip_train_etykiety.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out), encoding="utf-8")
    print(len(rows), "letters →", len(out), "with labels;",
          "deadline", Counter(x["expected"].get("termin") for x in out), "urgency", Counter(x["expected"].get("pilnosc") for x in out),
          "type", Counter(x["expected"].get("rodzaj") for x in out))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["urls", "labels"], help="urls: find notice URLs; labels: label downloaded notices")
    {"urls": collect_urls, "labels": make_labels}[ap.parse_args().command]()
