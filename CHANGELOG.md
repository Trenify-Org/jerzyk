# Changelog

## 1.0.0 — 2026

First public release.

- **Jerzyk 1.0** model (`trenify/jerzyk-1.0`): Laya multilingual (mmBERT encoder, 322M) fine-tuned on 2,340 Polish
  documents, calibrated on the dev split.
- **jerzyk-bench** (`trenify/jerzyk-bench`): generated and real test documents for four domains.
- **Python API**: `Jerzyk.ask()` (English names of questions and answers, `labels="pl"` for the model's Polish ones), `Jerzyk.predict()` (TypeSafe Jev `systemone` format), model download from Hugging Face.
- **`deadlines`**: rule-based extraction and computation of Polish deadlines (KC, KPC, KPA; Saturdays and public holidays).
- **Server and demo page**: `/v1/systemone`, `/api/demo`.
