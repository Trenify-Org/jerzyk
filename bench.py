"""Krok 0: porównanie modeli decyzyjnych na polskich pismach.

Użycie:
  python3 bench.py --name laya-ml --kind systemone --url http://127.0.0.1:9931
  python3 bench.py --name bielik --kind llm --url http://127.0.0.1:9932
"""
import argparse
import json
import math
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent

RODZAJE = {
    "wyrok": "orzeczenie sądu kończące sprawę co do istoty (wyrok)",
    "postanowienie": "postanowienie sądu (np. w sprawie zabezpieczenia, wpisu, kosztów)",
    "nakaz_zaplaty": "nakaz zapłaty w postępowaniu upominawczym lub nakazowym",
    "wezwanie_sadu": "wezwanie lub zobowiązanie sądu do wykonania czynności (uzupełnienie braków, odpowiedź na pozew)",
    "zawiadomienie_o_rozprawie": "zawiadomienie lub wezwanie na rozprawę albo posiedzenie",
    "pozew": "pozew lub wniosek wszczynający postępowanie",
    "odpowiedz_na_pozew": "odpowiedź na pozew lub inne pismo procesowe strony przeciwnej",
    "wezwanie_do_zaplaty": "przedsądowe wezwanie do zapłaty od wierzyciela",
    "faktura": "faktura lub rachunek",
    "inne": "inna korespondencja (e-mail klienta, informacja, zaproszenie)",
}
TERMIN_Q = ("Czy to pismo uruchamia termin, w którym kancelaria lub klient musi podjąć "
            "działanie (zapłata, środek odwoławczy, uzupełnienie braków, stawiennictwo, odpowiedź)?")
PILNOSC = [
    "niska – można odłożyć",
    "średnia – do zrobienia w tym tygodniu",
    "wysoka – w ciągu 1–2 dni",
    "krytyczna – krótki termin procesowy, zająć się natychmiast",
]
LETTERS = "ABCDEFGHIJKLMNOP"


def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


QUESTIONS = {
    "rodzaj": {"type": "choice", "instructions": "Jaki to rodzaj pisma?", "criteria": RODZAJE},
    "termin": {"type": "noul", "instructions": TERMIN_Q},
    "pilnosc": {"type": "score", "instructions": "Jak pilne jest to pismo dla kancelarii?",
                "criteria": PILNOSC},
}


def ask_systemone(url, tekst):
    return parse_answers(post(url + "/v1/systemone", {"state": tekst, "questions": QUESTIONS})["answers"])


_laya = {}


def ask_laya(model_id, tekst):
    """Laya uruchomiona lokalnie przez pakiet `laya` (PyTorch), bez serwera."""
    if model_id not in _laya:
        import laya
        _laya[model_id] = laya.load(model_id)
    return parse_answers(_laya[model_id].predict(tekst, QUESTIONS)["answers"])


def parse_answers(res):
    return {
        "rodzaj": res["rodzaj"]["probabilities"],
        "termin": res["termin"]["noul"],
        "pilnosc": [res["pilnosc"]["probabilities"][str(i)] if isinstance(res["pilnosc"]["probabilities"], dict)
                    else res["pilnosc"]["probabilities"][i] for i in range(len(PILNOSC))],
    }


def letter_probs(url, tekst, question, options):
    """Ocena opcji przez logprobs pierwszego tokenu odpowiedzi (jedna litera)."""
    lines = "\n".join(f"{LETTERS[i]}) {o}" for i, o in enumerate(options))
    res = post(url + "/v1/chat/completions", {
        "messages": [
            {"role": "system", "content": "Jesteś asystentem kancelarii prawnej. Odpowiadasz wyłącznie jedną literą."},
            {"role": "user", "content": f"Pismo:\n<<<\n{tekst}\n>>>\n\nPytanie: {question}\nOpcje:\n{lines}\n\nOdpowiedz jedną literą."},
        ],
        "max_tokens": 1, "temperature": 0, "logprobs": True, "top_logprobs": 20,
        "chat_template_kwargs": {"enable_thinking": False},
    })
    top = res["choices"][0]["logprobs"]["content"][0]["top_logprobs"]
    probs = [0.0] * len(options)
    for t in top:
        tok = t["token"].strip().rstrip(")")
        if len(tok) == 1 and tok in LETTERS[:len(options)]:
            probs[LETTERS.index(tok)] += math.exp(t["logprob"])
    s = sum(probs)
    return [p / s for p in probs] if s > 0 else [1 / len(options)] * len(options)


def ask_llm(url, tekst):
    keys = list(RODZAJE)
    rodzaj = letter_probs(url, tekst, "Jaki to rodzaj pisma?", [f"{k} – {v}" for k, v in RODZAJE.items()])
    termin = letter_probs(url, tekst, TERMIN_Q, ["tak", "nie"])
    pilnosc = letter_probs(url, tekst, "Jak pilne jest to pismo dla kancelarii?", PILNOSC)
    return {"rodzaj": dict(zip(keys, rodzaj)), "termin": termin[0], "pilnosc": pilnosc}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--kind", choices=["systemone", "llm", "laya"], required=True)
    ap.add_argument("--url", required=True, help="adres serwera albo, dla --kind laya, id modelu z HF")
    args = ap.parse_args()

    items = [json.loads(l) for l in (ROOT / "data/pisma.jsonl").read_text().splitlines() if l.strip()]
    ask = {"systemone": ask_systemone, "llm": ask_llm, "laya": ask_laya}[args.kind]
    ask(args.url, items[0]["tekst"])  # rozgrzewka

    rows = []
    for it in items:
        t0 = time.perf_counter()
        a = ask(args.url, it["tekst"])
        ms = (time.perf_counter() - t0) * 1000
        pred = max(a["rodzaj"], key=a["rodzaj"].get)
        p_lvl = max(range(len(PILNOSC)), key=lambda i: a["pilnosc"][i])
        exp_lvl = sum(i * p for i, p in enumerate(a["pilnosc"]))
        rows.append({
            "id": it["id"], "ms": round(ms),
            "rodzaj": it["rodzaj"], "rodzaj_pred": pred, "rodzaj_conf": round(a["rodzaj"][pred], 3),
            "termin": it["termin"], "termin_p": round(a["termin"], 3),
            "pilnosc": it["pilnosc"], "pilnosc_pred": p_lvl, "pilnosc_exp": round(exp_lvl, 2),
        })
        r = rows[-1]
        ok = "✓" if pred == it["rodzaj"] else "✗"
        print(f"{it['id']} {ok} {pred:26} {r['rodzaj_conf']:.2f} | termin p={r['termin_p']:.2f} "
              f"(jest {it['termin']}) | pilność {p_lvl} (jest {it['pilnosc']}) | {r['ms']} ms")

    n = len(rows)
    ok = [r for r in rows if r["rodzaj"] == r["rodzaj_pred"]]
    bad = [r for r in rows if r["rodzaj"] != r["rodzaj_pred"]]
    mean = lambda xs: sum(xs) / len(xs) if xs else float("nan")
    summary = {
        "model": args.name,
        "rodzaj_trafnosc": round(len(ok) / n, 3),
        "rodzaj_pewnosc_gdy_dobrze": round(mean([r["rodzaj_conf"] for r in ok]), 3),
        "rodzaj_pewnosc_gdy_zle": round(mean([r["rodzaj_conf"] for r in bad]), 3),
        "termin_trafnosc": round(mean([(r["termin_p"] >= 0.5) == r["termin"] for r in rows]), 3),
        "termin_brier": round(mean([(r["termin_p"] - r["termin"]) ** 2 for r in rows]), 3),
        "pilnosc_trafnosc": round(mean([r["pilnosc_pred"] == r["pilnosc"] for r in rows]), 3),
        "pilnosc_mae": round(mean([abs(r["pilnosc_exp"] - r["pilnosc"]) for r in rows]), 2),
        "ms_na_pismo_mediana": sorted(r["ms"] for r in rows)[n // 2],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    (out / f"{args.name}.json").write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
