# Jerzyk

**A small, fast Polish decision model. It does not write text: it reads a document and picks an answer from a fixed list, with a calibrated probability.**

> 🇵🇱 **Po polsku:** Jerzyk to mały (322 mln parametrów), szybki model AI dla polskich dokumentów. Czyta pismo z sądu lub urzędu, dokument księgowy albo e-mail klienta i odpowiada na pytania z gotową listą odpowiedzi: jaki to rodzaj pisma, czy biegnie termin, jak bardzo jest pilne, do którego działu je skierować. Każda odpowiedź ma prawdopodobieństwo, więc niepewne przypadki można oddać człowiekowi. Działa lokalnie, także na zwykłym laptopie bez karty graficznej (ok. 0,05–0,2 s na pismo), więc dokumenty nie opuszczają firmy. Licencja Apache 2.0. Razem z modelem udostępniamy **jerzyk-bench**, polski benchmark modeli decyzyjnych dla korespondencji urzędowej, i bibliotekę `deadlines.py`, która liczy terminy według KPC/KPA (soboty, święta).

```text
Document: "Sygn. akt I C 412/26 … wzywa się pełnomocnika powoda do uzupełnienia braków formalnych
           pozwu … w terminie 7 dni od doręczenia wezwania pod rygorem zwrotu pozwu."

rodzaj  (document type)     → wezwanie_sadu (court summons)     99.8%
termin  (deadline running?) → yes                               91.1%
pilnosc (urgency 0–3)       → 3 – critical (≤ 7 days)           99.2%
deadlines.py                → delivered 3 Nov 2026 → due 10 Nov 2026
```

## Why

Teams use large chat models for small decisions such as "invoice or contract?", "which department?" or "is there a deadline?". That is slow (seconds per document), expensive, risky for confidential documents (GDPR, legal privilege, the AI Act), and it needs output parsing, because a generative model can answer outside the list.

Jerzyk is a **decision model** (a classifier with typed questions):

- **Answers only from the list you give it**, with a probability for every option, calibrated on held-out data.
- **Runs locally** on CPU or GPU, in about 0.05–0.2 s per document.
- **Speaks the TypeSafe Jev / `systemone` API** (`POST /v1/systemone`), so tools built for Jev-style models work with it.
- **Specialised in Polish correspondence:** court letters, administrative notices and decisions, accounting documents, and customer e-mails.

## Results (jerzyk-bench)

**Generated test set (480 documents)** — accuracy (%)

| Question | **Jerzyk 1.0** (322M) | basal-2.0-mini (1.5B) | Qwen3 8B | Bielik 11B v3 |
|---|---|---|---|---|
| Administrative: pilnosc | 77.5 | 61.7 | 42.5 | 54.2 |
| Administrative: rodzaj | 90.0 | 92.5 | 90.8 | 95.0 |
| Administrative: termin | 82.5 | 79.2 | 84.2 | 83.3 |
| Customer e-mail: dzial | 93.3 | 88.3 | 89.2 | 88.3 |
| Customer e-mail: pilnosc | 79.2 | 74.2 | 70.8 | 80.8 |
| Customer e-mail: rezygnacja | 99.2 | 100.0 | 97.5 | 96.7 |
| Customer e-mail: zdenerwowany | 91.7 | 90.8 | 77.5 | 85.0 |
| Accounting: kategoria_kosztu | 97.5 | 95.0 | 85.0 | 75.8 |
| Accounting: pilnosc | 64.2 | 35.8 | 48.3 | 63.3 |
| Accounting: rodzaj | 94.2 | 91.7 | 95.8 | 95.8 |
| Accounting: termin | 85.8 | 95.8 | 94.2 | 77.5 |
| Court: pilnosc | 80.0 | 42.5 | 38.3 | 54.2 |
| Court: rodzaj | 84.2 | 96.7 | 94.2 | 92.5 |
| Court: termin | 93.3 | 85.0 | 83.3 | 82.5 |
| **Mean over domains** | **86.4** | **80.1** | **77.3** | **79.9** |

**Real documents (89 court rulings + 56 administrative notices)** — accuracy (%), 95% confidence interval in brackets

| Question | **Jerzyk 1.0** (322M) | basal-2.0-mini (1.5B) | Qwen3 8B | Bielik 11B v3 |
|---|---|---|---|---|
| Admin. notices (real): pilnosc | 69.6 | 42.9 | 37.5 | 16.1 |
| Admin. notices (real): rodzaj | 82.1 | 75.0 | 82.1 | 85.7 |
| Admin. notices (real): termin | 71.4 | 75.0 | 60.7 | 80.4 |
| Court rulings (real): rodzaj | 98.9 | 93.3 | 100.0 | 100.0 |
| **Mean over domains** | **86.6** | **78.8** | **80.0** | **80.4** |

| | **Jerzyk 1.0** (322M) | basal-2.0-mini (1.5B) | Qwen3 8B | Bielik 11B v3 |
|---|---|---|---|---|
| ECE, real documents (lower = better) | 0.101 | 0.116 | 0.228 | 0.181 |
| Median latency per document (all models on the same computer) | 0.05 s | 0.28 s | 1.75 s | 3.01 s |

How to read the table:

- **Jerzyk is best on average**, both on generated and on real documents, and is 5–60× faster than the other models.
- **Where it wins:** urgency (`pilnosc`; the rules follow 7/14-day thresholds in [`SPEC.md`](SPEC.md)), deadlines in court letters, routing questions (e-mail department, cost category) and calibration (ECE).
- **Where larger models win:** document type of generated court letters, and of real administrative notices (Bielik).
- **Known weakness: deadlines in long real administrative notices** (Jerzyk 71%, Bielik 80%). Always use Jerzyk together with `deadlines.py` (rule-based deadline extraction), and route low-confidence answers to a person.
- Jerzyk is trained on the conventions in `SPEC.md`. The other models see them for the first time (zero-shot), so the urgency comparison is not fully apples to apples.
- The generated test documents were written by Bielik 11B (court, administrative, accounting) and Claude (e-mails). Jerzyk's training data was written by a different model (Qwen3 8B) and comes from real documents from other offices.
- The real documents (court rulings from SAOS, public notices from samorzad.gov.pl) never overlap with training data. Notices in the test come from offices that do not appear in training.
- 31 court-ruling fragments that start mid-text, with no "WYROK"/"POSTANOWIENIE" header, are reported separately (`sad_real_fragmenty_test`). Jerzyk 1.0 scores 80.6% on them.

## Quick start

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.txt
# model: https://huggingface.co/trenify/jerzyk-1.0  → models/jerzyk-1.0
huggingface-cli download trenify/jerzyk-1.0 --local-dir models/jerzyk-1.0
```

**Python**

```python
from jerzyk import Jerzyk

j = Jerzyk("models/jerzyk-1.0")
j.ask("Dzień dobry, od rana nie mogę zalogować się do aplikacji i opłacić faktury…", domain="email")
# {'dzial': ('platnosci_i_faktury', 0.998), 'rezygnacja': (False, 0.943),
#  'zdenerwowany': (False, 0.675), 'pilnosc': (2, 0.623)}
```

Domains with ready-made questions: `court`, `admin` (administrative / building permits), `accounting`, `email` (customer e-mail). The Polish codes `sad`, `adm`, `ksieg` used in jerzyk-bench work too. You can also ask your own questions with `j.predict(text, questions)` in the `systemone` format (`choice`, `noul` = yes/no, `score`).

**Server + demo page**

```bash
USE_TF=0 .venv/bin/python jerzyk_serve.py --model models/jerzyk-1.0 --port 8080
open http://127.0.0.1:8080          # demo page
curl -s localhost:8080/v1/systemone -H 'content-type: application/json' -d '{
  "state": "Faktura VAT nr FV/12/2026 … termin płatności 14 dni",
  "questions": {"rodzaj": {"type": "choice", "instructions": "Jaki to dokument?",
                 "criteria": {"faktura": "faktura VAT", "umowa": "umowa", "inne": "inne"}}}}'
```

**Deadlines**

```python
import datetime as dt, deadlines
deadlines.nearest("… w terminie 7 dni od doręczenia …", delivery=dt.date(2026, 11, 3))
# Deadline(date=2026-11-10, kind='from_delivery', …) — Saturdays and public holidays shift the deadline (KPC/KPA)
```

**Glossary.** Question names and answer options stay in Polish, because the model was trained on them.

| Name | Meaning |
|---|---|
| `sad`, `adm`, `ksieg`, `email` | domain codes in jerzyk-bench: court, administrative, accounting, customer e-mail |
| `rodzaj` | document type |
| `termin` | is a deadline for the recipient running? (yes/no) |
| `pilnosc` | urgency: 0 nothing to do, 1 no deadline or > 14 days, 2 8–14 days, 3 ≤ 7 days or immediately |
| `kategoria_kosztu` | cost category (accounting) |
| `dzial`, `rezygnacja`, `zdenerwowany` | e-mail: department, cancels or terminates?, customer upset? |

## What is in this repository

| File | Purpose |
|---|---|
| `jerzyk.py`, `jerzyk_serve.py`, `demo/` | Python API, HTTP server (`/v1/systemone`, `/api/demo`), demo page |
| `test_jerzyk.py` | Tests of calibration and the Python API (no model needed) |
| `deadlines.py`, `test_deadlines.py` | Polish deadline extraction and computation (KC/KPC/KPA, Saturdays, holidays incl. Christmas Eve from 2025) |
| `SPEC.md`, `tasks.py` | jerzyk-bench specification: questions, answer options, labelling rules and all decisions taken |
| `gen_bench.py`, `precheck.py`, `review.py` | Generated test set: labels by construction from recipes, automatic checks, manual review in the terminal |
| `saos.py`, `saos_2025.py`, `bip*.py`, `prawo.py` | Real documents: SAOS court rulings, public notices from samorzad.gov.pl |
| `train_v1.py`, `run_v4.sh`, `calibrate.py` | Training data (generator, filter, build), training, temperature calibration on dev |
| `evaluate.py`, `tabela.py`, `run_basal.sh` | Evaluation of any model (Jerzyk, `systemone` servers, LLMs via llama.cpp) and the results table |
| `TRENING.md` | How to reproduce or improve the model on a Mac, an NVIDIA GPU or in the cloud (Polish) |

## How it was built

1. **Specification first.** [`SPEC.md`](SPEC.md) defines every question and the labelling rules. For example: an invoice payment term is not a "deadline"; urgency 3 means ≤ 7 days; a threat of court in an e-mail means the customer is upset.
2. **Labels by construction.** The generator gets a recipe (document type, deadline, urgency) and writes a document that matches it. Automatic checks and a second model reject documents that drift from the recipe.
3. **Real documents.** About 500 court rulings from SAOS with document type from metadata, and 84 public notices from municipal and county offices, with deadline and urgency from rules. The rules agree with manual labels in 91% of cases.
4. **Fine-tuning** of [Laya multilingual](https://huggingface.co/convaiinnovations/laya-multilingual) (322M, mmBERT encoder) for 4 epochs.
5. **Calibration.** One temperature per question type, fitted on the dev split, never on the test split.

No training data comes from closed-model APIs. Generators and filters are open-weight Apache-2.0 models (Qwen3, Bielik), plus official documents.

## Limitations

- Polish documents only. Input is truncated to about 1024 tokens (about 3,000 characters), so a deadline at the end of a long notice may be missed.
- Not legal advice. Jerzyk helps sort and prioritise correspondence. A person must check deadlines and decisions with consequences, especially low-confidence ones.
- The real-document test set is small (145 documents). The 56 administrative notices were labelled following `SPEC.md` with Claude's help, and human review is in progress.
- Urgency follows the conventions in `SPEC.md`. Your organisation may need different thresholds, so retrain on your own data as described in `TRENING.md`.

## About

Jerzyk and jerzyk-bench are published by **Fundacja Trenify** (Trenify Foundation), a Polish non-profit foundation. Issues and pull requests are welcome on [GitHub](https://github.com/Trenify-Org/jerzyk).

## Citation

```bibtex
@misc{jerzyk2026,
  title        = {Jerzyk: a small Polish decision model for official correspondence, and jerzyk-bench},
  author       = {{Fundacja Trenify}},
  year         = {2026},
  howpublished = {\url{https://github.com/Trenify-Org/jerzyk}}
}
```

## License

Apache License 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE) for third-party models and data sources (Laya, mmBERT, Bielik, Qwen3, SAOS, samorzad.gov.pl).
