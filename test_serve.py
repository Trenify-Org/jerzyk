"""Tests for jerzyk_serve.py with a fake model (needs fastapi and httpx, not laya).

  python3 -m unittest test_serve
"""
import unittest

from fastapi.testclient import TestClient

import jerzyk_serve
from test_jerzyk import _Agent


class _Broken:
    @staticmethod
    def predict(state, qs):
        raise KeyError("internal_key_name")


def _client(agent=None):
    jerzyk_serve.STATE.update(agent=agent or _Agent(), name="fake", calibration={})
    return TestClient(jerzyk_serve.app)


class TestDemo(unittest.TestCase):
    def test_answers_and_deadlines(self):
        r = _client().post("/api/demo", json={"domain": "court", "delivery_date": "2026-11-03",
                                               "text": "… w terminie 7 dni od doręczenia …"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["nearest"], "2026-11-10")
        self.assertIn("rodzaj", r.json()["answers"])

    def test_bad_input_is_400(self):
        c = _client()
        for body in ({"domain": "medical", "text": "x"}, {"domain": "court", "text": "  "},
                     {"domain": "court", "text": "x", "delivery_date": "3.11.2026"}):
            self.assertEqual(c.post("/api/demo", json=body).status_code, 400, body)

    def test_too_long_text_is_rejected(self):
        r = _client().post("/api/demo", json={"domain": "court", "text": "a" * (jerzyk_serve.MAX_TEXT + 1)})
        self.assertEqual(r.status_code, 422)


class TestSystemOne(unittest.TestCase):
    QS = {"termin": {"type": "noul", "instructions": "Czy biegnie termin?"}}

    def test_answers(self):
        r = _client().post("/v1/systemone", json={"state": "tekst", "questions": self.QS})
        self.assertEqual(r.status_code, 200)
        self.assertIn("termin", r.json()["answers"])

    def test_too_many_questions(self):
        qs = {f"q{i}": self.QS["termin"] for i in range(jerzyk_serve.MAX_QUESTIONS + 1)}
        self.assertEqual(_client().post("/v1/systemone", json={"state": "x", "questions": qs}).status_code, 422)

    def test_too_large_state(self):
        r = _client().post("/v1/systemone", json={"state": {"t": "a" * (jerzyk_serve.MAX_TEXT + 1)}, "questions": self.QS})
        self.assertEqual(r.status_code, 422)

    def test_error_does_not_leak_internals(self):
        r = _client(_Broken()).post("/v1/systemone", json={"state": "x", "questions": self.QS})
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("internal_key_name", r.text)


class TestHostWarning(unittest.TestCase):
    def test_only_loopback_is_quiet(self):
        for host in ("127.0.0.1", "localhost", "::1"):
            self.assertFalse(jerzyk_serve.exposed(host))
        for host in ("0.0.0.0", "192.168.1.10", "::"):
            self.assertTrue(jerzyk_serve.exposed(host))


if __name__ == "__main__":
    unittest.main()
