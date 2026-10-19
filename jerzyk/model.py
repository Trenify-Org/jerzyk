"""Jerzyk in Python: the model, its calibration and ready-made questions for four domains.

  from jerzyk import Jerzyk
  j = Jerzyk("trenify/jerzyk-1.0")          # downloads from Hugging Face; or a local folder
  j.ask("Sąd Rejonowy … w terminie 7 dni od doręczenia …", domain="court")
  # {'document_type': ('court_summons', 0.97), 'deadline': (True, 0.95), 'urgency': (3, 0.91)}

Domains: court, admin, accounting, email (Polish codes sad, adm, ksieg, email also work).
Answers come with English names (jerzyk.labels); labels="pl" gives the Polish names the model was trained on
and jerzyk-bench uses, e.g. {'rodzaj': ('wezwanie_sadu', 0.97), 'termin': …, 'pilnosc': …}.
"""
import copy
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple, Union

from jerzyk.labels import to_english
from jerzyk.questions import questions

# English domain name → code used by jerzyk.questions, jerzyk-bench and the model
DOMAINS = {"court": "sad", "admin": "adm", "accounting": "ksieg", "email": "email"}
CALIBRATION_FILES = ("calibration.json", "kalibracja.json")  # kalibracja.json: name used before 1.0
DEFAULT_MODEL = "trenify/jerzyk-1.0"
LABELS = ("en", "pl")
_HUB_ID = re.compile(r"[A-Za-z0-9][\w.-]*/[\w.-]+")


def _hub_download(repo_id: str) -> str:
    from huggingface_hub import snapshot_download
    return snapshot_download(repo_id)


def resolve_model(model: Union[str, Path], download: Optional[Callable[[str], str]] = None) -> Path:
    """Local model folder, or a Hugging Face id ("trenify/jerzyk-1.0") downloaded to the local cache."""
    if Path(model).exists():
        return Path(model)
    if isinstance(model, str) and _HUB_ID.fullmatch(model):
        return Path((download or _hub_download)(model))
    raise FileNotFoundError(f"model not found: {model} (a local folder or a Hugging Face id such as {DEFAULT_MODEL})")


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
            return json.loads(f.read_text(encoding="utf-8"))
    return {}


def calibrate(res: Dict[str, Any], qs: Dict[str, Any], temperatures: Dict[str, float]) -> Dict[str, Any]:
    """Temperature scaling (scripts/calibrate.py): p_i ∝ p_i^(1/T), one T per question type. Returns a new answer."""
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
    """Jerzyk running locally. `model` is a Hugging Face id or a folder with the weights and calibration.json."""

    def __init__(self, model: Union[str, Path] = DEFAULT_MODEL):
        import laya
        path = resolve_model(model)
        self.agent = laya.load(str(path))
        self.temperatures = load_calibration(path)

    def predict(self, state: str, qs: Dict[str, Any]) -> Dict[str, Any]:
        """Full calibrated answer in the /v1/systemone format (TypeSafe Jev) for your own questions."""
        return calibrate(self.agent.predict(state, qs), qs, self.temperatures)

    def ask(self, text: str, domain: str = "court", labels: str = "en") -> Dict[str, Tuple[Any, float]]:
        """Short form: {question: (answer, confidence)} for the ready-made questions of a domain.

        labels="en" (default) names questions and answers in English, labels="pl" in the model's Polish."""
        if labels not in LABELS:
            raise ValueError(f"labels must be one of {LABELS}, not {labels!r}")
        code = resolve_domain(domain)
        qs = questions(code)
        out = {}
        for qid, a in self.predict(text, qs)["answers"].items():
            if a["type"] == "noul":
                out[qid] = (a["noul"] >= 0.5, a["confidence"])
            elif a["type"] == "score":
                p = a["probabilities"]
                out[qid] = (int(max(p, key=p.get)), a["confidence"])
            else:
                out[qid] = (a["choice"], a["confidence"])
        return to_english(out, code) if labels == "en" else out
