"""Jerzyk in Python: the model, its calibration and ready-made questions for four domains.

  from jerzyk import Jerzyk
  j = Jerzyk("models/jerzyk-1.0")
  j.ask("Sąd Rejonowy … w terminie 7 dni od doręczenia …", domain="court")
  # {'rodzaj': ('wezwanie_sadu', 0.97), 'termin': (True, 0.95), 'pilnosc': (3, 0.91)}

Domains: court, admin, accounting, email (Polish codes sad, adm, ksieg, email also work).
Questions: rodzaj = document type, termin = is a deadline running, pilnosc = urgency 0–3,
kategoria_kosztu = cost category, dzial = department, rezygnacja = cancels?, zdenerwowany = upset?
Question names and answer options stay in Polish: the model was trained on them (questions.json).
"""
import copy
import json
from pathlib import Path
from typing import Any, Dict, Tuple, Union

from tasks import questions

# English domain name → code used by tasks.py, jerzyk-bench and the model
DOMAINS = {"court": "sad", "admin": "adm", "accounting": "ksieg", "email": "email"}
CALIBRATION_FILES = ("calibration.json", "kalibracja.json")  # kalibracja.json: name used before 1.0


def resolve_domain(domain: str) -> str:
    """English or Polish domain name → Polish code (court → sad). Raises ValueError for an unknown domain."""
    if domain in DOMAINS.values():
        return domain
    if domain in DOMAINS:
        return DOMAINS[domain]
    raise ValueError(f"unknown domain {domain!r}; use one of {', '.join(DOMAINS)}")


def load_calibration(model: Union[str, Path]) -> Dict[str, float]:
    """Temperatures {question type: T} from the model folder; {} (no calibration) if the file is missing."""
    for name in CALIBRATION_FILES:
        f = Path(model) / name
        if f.exists():
            return json.loads(f.read_text())
    return {}


def calibrate(res: Dict[str, Any], qs: Dict[str, Any], temperatures: Dict[str, float]) -> Dict[str, Any]:
    """Temperature scaling (calibrate.py): p_i ∝ p_i^(1/T), one T per question type. Returns a new answer."""
    res = copy.deepcopy(res)
    for qid, a in res.get("answers", {}).items():
        t = (temperatures or {}).get(a.get("type") or qs.get(qid, {}).get("type"), 1.0)
        if t == 1.0:
            continue
        if a.get("type") == "noul":
            p = min(max(a["noul"], 1e-9), 1 - 1e-9)
            p = p ** (1 / t) / (p ** (1 / t) + (1 - p) ** (1 / t))
            a["noul"], a["confidence"] = round(p, 4), round(max(p, 1 - p), 4)
        elif "probabilities" in a:
            w = {k: max(v, 1e-9) ** (1 / t) for k, v in a["probabilities"].items()}
            a["probabilities"] = {k: round(v / sum(w.values()), 4) for k, v in w.items()}
            a["confidence"] = max(a["probabilities"].values())
            if a.get("type") == "choice":
                a["choice"] = max(a["probabilities"], key=a["probabilities"].get)
            if a.get("type") == "score":
                a["score"] = round(sum(int(k) * v for k, v in a["probabilities"].items()), 4)
    return res


class Jerzyk:
    """A local Jerzyk model. `model` is a folder with the weights and calibration.json."""

    def __init__(self, model: Union[str, Path] = "models/jerzyk-1.0"):
        import laya
        self.agent = laya.load(str(model))
        self.temperatures = load_calibration(model)

    def predict(self, state: str, qs: Dict[str, Any]) -> Dict[str, Any]:
        """Full calibrated answer in the /v1/systemone format (TypeSafe Jev) for your own questions."""
        return calibrate(self.agent.predict(state, qs), qs, self.temperatures)

    def ask(self, text: str, domain: str = "court") -> Dict[str, Tuple[Any, float]]:
        """Short form: {question: (answer, confidence)} for the ready-made questions of a domain."""
        qs = questions(resolve_domain(domain))
        out = {}
        for qid, a in self.predict(text, qs)["answers"].items():
            if a["type"] == "noul":
                out[qid] = (a["noul"] >= 0.5, a["confidence"])
            elif a["type"] == "score":
                p = a["probabilities"]
                out[qid] = (int(max(p, key=p.get)), a["confidence"])
            else:
                out[qid] = (a["choice"], a["confidence"])
        return out

    def zapytaj(self, tekst: str, domena: str = "sad") -> Dict[str, Tuple[Any, float]]:
        """Polish alias of `ask`."""
        return self.ask(tekst, domain=domena)
