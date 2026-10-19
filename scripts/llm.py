"""Shared helpers for calling an LLM server (OpenAI-compatible chat API) from the benchmark and training scripts.

  from scripts.llm import post, letter_probs
"""
import json
import math
import urllib.request

LETTERS = "ABCDEFGHIJKLMNOP"


def post(url, payload):
    """POST a JSON payload and return the decoded JSON response."""
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def letter_probs(url, text, question, options):
    """Score the options from the logprobs of the first answer token (a single letter)."""
    lines = "\n".join(f"{LETTERS[i]}) {o}" for i, o in enumerate(options))
    res = post(url + "/v1/chat/completions", {
        "messages": [
            {"role": "system", "content": "Jesteś asystentem kancelarii prawnej. Odpowiadasz wyłącznie jedną literą."},
            {"role": "user", "content": f"Pismo:\n<<<\n{text}\n>>>\n\nPytanie: {question}\nOpcje:\n{lines}\n\nOdpowiedz jedną literą."},
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
