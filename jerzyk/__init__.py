"""Jerzyk — a small Polish decision model for official correspondence.

    from jerzyk import Jerzyk
    j = Jerzyk("trenify/jerzyk-1.0")
    j.ask("…tekst pisma…", domain="court")

Modules: jerzyk.model (the model and calibration), jerzyk.questions (ready-made questions),
jerzyk.labels (their English names), jerzyk.deadlines (rule-based Polish deadlines), jerzyk.serve (HTTP server and demo page).
"""
from jerzyk.model import DEFAULT_MODEL, DOMAINS, Jerzyk, calibrate, load_calibration, resolve_domain, resolve_model

__version__ = "1.0.0"
__all__ = ["DEFAULT_MODEL", "DOMAINS", "Jerzyk", "calibrate", "load_calibration", "resolve_domain", "resolve_model"]
