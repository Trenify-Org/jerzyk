"""jerzyk.serve — local Jerzyk server: TypeSafe Jev-compatible API (/v1/systemone) and a demo page.

  jerzyk-serve --port 8080                      # model trenify/jerzyk-1.0 from Hugging Face
  jerzyk-serve --model models/jerzyk-1.0        # or: python -m jerzyk.serve …
  open http://127.0.0.1:8080

The server has no authentication. Keep the default --host 127.0.0.1 unless it runs behind your own access control.
"""
import argparse
import datetime as dt
import ipaddress
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from jerzyk import deadlines
from jerzyk.model import DEFAULT_MODEL, calibrate, load_calibration, resolve_domain, resolve_model
from jerzyk.questions import questions

ROOT = Path(__file__).parent
MAX_TEXT = 100_000      # characters; the model reads only about the first 3,000 anyway
MAX_QUESTIONS = 32
MAX_QUESTION_JSON = 20_000

log = logging.getLogger("jerzyk")
app = FastAPI(title="Jerzyk", version="1.0")
STATE: Dict[str, Any] = {}
_MODEL_LOCK = threading.Lock()  # one prediction at a time: the model object is shared between request threads


class SystemOneRequest(BaseModel):
    state: Any
    questions: Dict[str, Dict[str, Any]] = Field(min_length=1, max_length=MAX_QUESTIONS)

    @field_validator("state")
    @classmethod
    def _state_size(cls, v):
        if len(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)) > MAX_TEXT:
            raise ValueError(f"state longer than {MAX_TEXT} characters")
        return v

    @field_validator("questions")
    @classmethod
    def _questions_size(cls, v):
        if any(len(json.dumps(q, ensure_ascii=False)) > MAX_QUESTION_JSON for q in v.values()):
            raise ValueError(f"a question is longer than {MAX_QUESTION_JSON} characters")
        return v


class DemoRequest(BaseModel):
    domain: str = Field(max_length=32)                          # court, admin, accounting, email (or sad, adm, ksieg)
    text: str = Field(max_length=MAX_TEXT)
    delivery_date: Optional[str] = Field(default=None, max_length=10)  # YYYY-MM-DD


def _predict(state: Any, qs: Dict[str, Any]) -> Dict[str, Any]:
    with _MODEL_LOCK:
        return calibrate(STATE["agent"].predict(state, qs), qs, STATE["calibration"])


def exposed(host: str) -> bool:
    """True if the server would be reachable from other machines (anything but loopback)."""
    if host == "localhost":
        return False
    try:
        return not ipaddress.ip_address(host).is_loopback
    except ValueError:
        return True


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "model": STATE["name"]}


@app.post("/v1/systemone")
def systemone(req: SystemOneRequest) -> Dict[str, Any]:
    """Same contract as TypeSafe Jev and llama.cpp: state + questions → answers + usage."""
    try:
        return _predict(req.state, req.questions)
    except (ValueError, KeyError, TypeError):
        log.exception("invalid /v1/systemone request")
        raise HTTPException(status_code=400, detail="invalid questions: see the systemone format in the README")


@app.post("/api/demo")
def demo(req: DemoRequest) -> Dict[str, Any]:
    """Demo page backend: ready-made questions of a domain plus deadlines found by jerzyk.deadlines."""
    try:
        domain = resolve_domain(req.domain)
        delivery = dt.date.fromisoformat(req.delivery_date) if req.delivery_date else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))  # our own messages: unknown domain, bad date
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="empty text")
    qs = questions(domain)
    t0 = time.perf_counter()
    res = _predict(req.text, qs)
    ms = round((time.perf_counter() - t0) * 1000)

    found = deadlines.find(req.text, delivery)
    first = deadlines.nearest(req.text, delivery)
    return {
        "model": STATE["name"], "ms": ms, "questions": qs, "answers": res["answers"],
        "deadlines": [{"date": d.date.isoformat() if d.date else None, "kind": d.kind, "fragment": d.fragment}
                      for d in found],
        "nearest": first.date.isoformat() if first and first.date else None,
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "demo" / "index.html")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL, help="Hugging Face id or local folder")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)
    if exposed(args.host):
        log.warning("--host %s makes the server reachable from other machines. It has no authentication: "
                    "use it only behind your own access control.", args.host)
    import laya
    path = resolve_model(args.model)
    STATE["agent"] = laya.load(str(path))
    STATE["name"] = Path(str(args.model)).name
    STATE["calibration"] = load_calibration(path)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
