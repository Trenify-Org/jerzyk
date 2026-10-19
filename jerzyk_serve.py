"""jerzyk serve — local Jerzyk server: TypeSafe Jev-compatible API (/v1/systemone) and a demo page.

  USE_TF=0 .venv/bin/python jerzyk_serve.py --model models/jerzyk-1.0 --port 8080
  open http://127.0.0.1:8080
"""
import argparse
import datetime as dt
import time
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import deadlines
from jerzyk import calibrate, load_calibration, resolve_domain
from tasks import questions

ROOT = Path(__file__).parent
app = FastAPI(title="Jerzyk", version="1.0")
STATE: Dict[str, Any] = {}


class SystemOneRequest(BaseModel):
    state: Any
    questions: Dict[str, Dict[str, Any]]


class DemoRequest(BaseModel):
    domain: str                          # court, admin, accounting, email (or sad, adm, ksieg)
    text: str
    delivery_date: Optional[str] = None  # YYYY-MM-DD


@app.get("/health")
def health():
    return {"status": "ok", "model": STATE["name"]}


@app.post("/v1/systemone")
def systemone(req: SystemOneRequest):
    """Same contract as TypeSafe Jev and llama.cpp: state + questions → answers + usage."""
    try:
        return calibrate(STATE["agent"].predict(req.state, req.questions), req.questions, STATE["calibration"])
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/demo")
def demo(req: DemoRequest):
    """Demo page backend: ready-made questions of a domain plus deadlines found by deadlines.py."""
    try:
        domain = resolve_domain(req.domain)
        delivery = dt.date.fromisoformat(req.delivery_date) if req.delivery_date else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="empty text")
    qs = questions(domain)
    t0 = time.perf_counter()
    res = calibrate(STATE["agent"].predict(req.text, qs), qs, STATE["calibration"])
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
def index():
    return FileResponse(ROOT / "demo" / "index.html")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/jerzyk-1.0")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()
    import laya
    STATE["agent"] = laya.load(args.model)
    STATE["name"] = Path(args.model).name
    STATE["calibration"] = load_calibration(args.model)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
