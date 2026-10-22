# Changelog

## 1.0.1 — 2026-10-22

Same model weights as 1.0.0. Only the reported results changed.

- **Results re-measured on the published version of jerzyk-bench** (text after anonymisation): Jerzyk 1.0, Qwen3 8B and
  Bielik 11B on an NVIDIA RTX 5080 Laptop GPU, basal-2.0-mini on an Apple M1 (MLX). Jerzyk 1.0 scores 86.4% on generated
  and 85.5% on real documents (85.8% before anonymisation); the ranking of the models is unchanged.
- **basal-2.0-mini** added to the re-measured tables; its latency is labelled with the machine it was measured on.
- **95% confidence intervals** for the real documents in the results tables.

## 1.0.0 — 2026

First public release.

- **Jerzyk 1.0** model (`trenify/jerzyk-1.0`): Laya multilingual (mmBERT encoder, 322M) fine-tuned on 2,340 Polish
  documents, calibrated on the dev split.
- **jerzyk-bench** (`trenify/jerzyk-bench`): generated and real test documents for four domains.
- **Python API**: `Jerzyk.ask()` (English names of questions and answers, `labels="pl"` for the model's Polish ones), `Jerzyk.predict()` (TypeSafe Jev `systemone` format), model download from Hugging Face.
- **`deadlines`**: rule-based extraction and computation of Polish deadlines (KC, KPC, KPA; Saturdays and public holidays).
- **Server and demo page**: `/v1/systemone`, `/api/demo`.
