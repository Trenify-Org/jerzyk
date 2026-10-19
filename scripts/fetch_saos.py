"""Downloads real common-court rulings from SAOS (saos.org.pl) as letters for the benchmark and training.

  python -m scripts.fetch_saos --count 300                                          # data/real/saos.jsonl (training)
  python -m scripts.fetch_saos --count 120 --out saos_test.jsonl --skip saos.jsonl  # test, without training rulings

Rulings are official documents (art. 4 of the Polish Copyright Act), already anonymised in SAOS. We save the beginning
(header + sentence) and the instruction on appeal (POUCZENIE), if present — this is what the office reads on the first page.
"""
import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://www.saos.org.pl/api/search/judgments"
REAL = Path(__file__).resolve().parent.parent / "data" / "real"
TYPE_LABELS = {"DECISION": "postanowienie", "SENTENCE": "wyrok"}
# Civil, commercial and labour divisions — offices receive the most letters there.
QUERIES = [("DECISION", "CIVIL"), ("SENTENCE", "CIVIL"), ("DECISION", "LABOUR_SOCIAL"), ("SENTENCE", "LABOUR_SOCIAL")]


def get(params):
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params),
                                 headers={"Accept": "application/json", "User-Agent": "jerzyk-bench/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def excerpt(text, n=1600):
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    head = text[:n]
    m = re.search(r"POUCZENIE.{0,700}", text[n:], re.S | re.I)
    return head + ("\n[...]\n" + m.group(0) if m else "")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=300)
    parser.add_argument("--out", default="saos.jsonl", help="file in data/real/")
    parser.add_argument("--skip", nargs="*", default=[], help="files in data/real/ with rulings to skip")
    args = parser.parse_args()
    out_path = REAL / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    for name in [args.out] + args.skip:  # training and test sets stay disjoint
        if (REAL / name).exists():
            seen |= {json.loads(line)["saos_id"] for line in (REAL / name).read_text().splitlines()}
    per_query = args.count // len(QUERIES)
    with out_path.open("a") as f:
        for kind, category in QUERIES:
            saved, page = 0, 0
            while saved < per_query:
                response = get({"pageSize": 50, "pageNumber": page, "courtType": "COMMON", "judgmentTypes": kind, "judgmentDateFrom": "2024-01-01",
                                "sortingField": "JUDGMENT_DATE", "sortingDirection": "DESC",
                                "all": "cywilny" if category == "CIVIL" else "pracy"})
                if not response["items"]:
                    break
                for item in response["items"]:
                    if item["id"] in seen or len(item.get("textContent", "")) < 400 or saved >= per_query:
                        continue
                    seen.add(item["id"])
                    f.write(json.dumps({
                        "saos_id": item["id"], "source": f"https://www.saos.org.pl/judgments/{item['id']}",
                        "case_number": item["courtCases"][0]["caseNumber"], "date": item["judgmentDate"],
                        "saos_type": TYPE_LABELS[kind], "state": excerpt(item["textContent"]),
                    }, ensure_ascii=False) + "\n")
                    saved += 1
                page += 1
                time.sleep(0.5)  # don't overload the service
            print(f"{kind}/{category}: {saved}", flush=True)


if __name__ == "__main__":
    main()
