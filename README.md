# Jerzyk

**A small, fast Polish decision model. It does not write text: it reads a document and picks an answer from a fixed list, with a calibrated probability.**

> 🇵🇱 **Po polsku:** Jerzyk to mały (322 mln parametrów), szybki model AI dla polskich dokumentów. Czyta pismo z sądu lub urzędu, dokument księgowy albo e-mail klienta i odpowiada na pytania z gotową listą odpowiedzi: jaki to rodzaj pisma, czy biegnie termin, jak bardzo jest pilne, do którego działu je skierować. Działa lokalnie, także na laptopie bez karty graficznej. Licencja Apache 2.0. Razem z modelem udostępniamy **jerzyk-bench**, polski benchmark modeli decyzyjnych, oraz moduł `jerzyk.deadlines`, który liczy terminy według KPC/KPA (soboty, święta).

```text
Document: "Sygn. akt I C 412/26 … wzywa się pełnomocnika powoda do uzupełnienia braków formalnych
           pozwu … w terminie 7 dni od doręczenia wezwania pod rygorem zwrotu pozwu."

document_type → court_summons                             99.8%
deadline      → yes                                       91.2%
urgency (0–3) → 3 – critical (≤ 7 days)                   92.8%
deadlines     → delivered 3 Nov 2026 → due 10 Nov 2026
```

## Quick start

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e ".[serve]"
# or straight from GitHub:
# pip install "jerzyk[serve] @ git+https://github.com/Trenify-Org/jerzyk"
# the model (trenify/jerzyk-1.0, 650 MB) downloads from Hugging Face on first use
```

**Python**

```python
from jerzyk import Jerzyk

j = Jerzyk("trenify/jerzyk-1.0")   # or a local folder
j.ask("Dzień dobry, od rana nie mogę zalogować się do aplikacji i opłacić faktury…", domain="email")
# {'department': ('payments_and_invoices', 0.998), 'cancellation': (False, 0.950),
#  'upset': (False, 0.636), 'urgency': (2, 0.551)}
# labels="pl" gives the model's Polish names: {'dzial': ('platnosci_i_faktury', 0.998), …}
```

Domains with ready-made questions: `court`, `admin` (administrative / building permits), `accounting`, `email` (customer e-mail). The Polish codes `sad`, `adm`, `ksieg` used in jerzyk-bench work too. You can also ask your own questions with `j.predict(text, questions)` in the `systemone` format (`choice`, `noul` = yes/no, `score`).

**Server + demo page**

```bash
USE_TF=0 jerzyk-serve --port 8080      # or: python -m jerzyk.serve --port 8080; --model trenify/jerzyk-1.0 or a local folder
open http://127.0.0.1:8080             # demo page
curl -s localhost:8080/v1/systemone -H 'content-type: application/json' -d '{
  "state": "Faktura VAT nr FV/12/2026 … termin płatności 14 dni",
  "questions": {"document_type": {"type": "choice", "instructions": "Jaki to dokument?",
                 "criteria": {"faktura": "faktura VAT", "umowa": "umowa", "inne": "inne"}}}}'
```

The server has no authentication and listens only on `127.0.0.1`. Do not expose it with `--host 0.0.0.0` unless it runs behind your own access control (see [`SECURITY.md`](SECURITY.md)).

**Tests** (no model needed): `python -m unittest discover -s tests -t .`

**Deadlines**

```python
import datetime as dt
from jerzyk import deadlines

deadlines.nearest("… w terminie 7 dni od doręczenia …", delivery=dt.date(2026, 11, 3))
# Deadline(date=2026-11-10, kind='from_delivery', …) — Saturdays and public holidays shift the deadline (KPC/KPA)
```

**Questions and answers.**

| Domain | Questions (`ask()` names; Polish names with `labels="pl"`) |
|---|---|
| `court` (`sad`) | `document_type` (`rodzaj`): judgment, court_decision, payment_order, court_summons, hearing_notice, statement_of_claim, party_letter, other · `deadline` (`termin`) · `urgency` (`pilnosc`) |
| `admin` (`adm`) | `document_type`: decision, procedural_decision, request_to_complete, notice, objection_to_notification, agreement_or_opinion, project_correspondence, other · `deadline` · `urgency` |
| `accounting` (`ksieg`) | `document_type`: invoice, corrective_invoice, receipt, accounting_note, bank_statement, contract, tax_office_letter, social_insurance_letter, payment_demand, other · `cost_category` (`kategoria_kosztu`): goods_for_resale, materials, external_services, utilities_and_telecom, fuel_and_car, rent, training, entertainment, fixed_asset, not_applicable · `deadline` · `urgency` |
| `email` (customer e-mail) | `department` (`dzial`): sales, orders_and_deliveries, complaints_and_returns, payments_and_invoices, technical_support, other · `cancellation` (`rezygnacja`) · `upset` (`zdenerwowany`) · `urgency` |

`deadline` = does the letter set or open a deadline for the recipient (yes/no). `urgency` 0–3: nothing to do / no deadline or > 14 days / 8–14 days / ≤ 7 days or immediately. Full rules: `SPEC.md`.

The model itself reads Polish questions and answer options (it was trained on them, see `jerzyk/questions.py`); `ask()` translates the result to English afterwards (`jerzyk/labels.py`), which does not change any prediction. jerzyk-bench uses the Polish names.

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
| Administrative: urgency | 77.5 | 61.7 | 42.5 | 54.2 |
| Administrative: document_type | 90.0 | 92.5 | 90.8 | 95.0 |
| Administrative: deadline | 82.5 | 79.2 | 84.2 | 83.3 |
| Customer e-mail: department | 93.3 | 88.3 | 89.2 | 88.3 |
| Customer e-mail: urgency | 79.2 | 74.2 | 70.8 | 80.8 |
| Customer e-mail: cancellation | 99.2 | 100.0 | 97.5 | 96.7 |
| Customer e-mail: upset | 91.7 | 90.8 | 77.5 | 85.0 |
| Accounting: cost_category | 97.5 | 95.0 | 85.0 | 75.8 |
| Accounting: urgency | 64.2 | 35.8 | 48.3 | 63.3 |
| Accounting: document_type | 94.2 | 91.7 | 95.8 | 95.8 |
| Accounting: deadline | 85.8 | 95.8 | 94.2 | 77.5 |
| Court: urgency | 80.0 | 42.5 | 38.3 | 54.2 |
| Court: document_type | 84.2 | 96.7 | 94.2 | 92.5 |
| Court: deadline | 93.3 | 85.0 | 83.3 | 82.5 |
| **Mean over domains** | **86.4** | **80.1** | **77.3** | **79.9** |

**Real documents (89 court rulings + 56 administrative notices)** — accuracy (%), 95% confidence interval in brackets

| Question | **Jerzyk 1.0** (322M) | basal-2.0-mini (1.5B) | Qwen3 8B | Bielik 11B v3 |
|---|---|---|---|---|
| Admin. notices (real): urgency | 58.9 (46–71) | 37.5 (26–51) | 48.2 (36–61) | 32.1 (21–45) |
| Admin. notices (real): document_type | 85.7 (74–93) | 76.8 (64–86) | 83.9 (72–91) | 85.7 (74–93) |
| Admin. notices (real): deadline | 73.2 (60–83) | 76.8 (64–86) | 62.5 (49–74) | 82.1 (70–90) |
| Court rulings (real): document_type | 98.9 (94–100) | 93.3 (86–97) | 100.0 (96–100) | 100.0 (96–100) |
| **Mean over domains** | **85.8** | **78.5** | **82.4** | **83.3** |

| | **Jerzyk 1.0** (322M) | basal-2.0-mini (1.5B) | Qwen3 8B | Bielik 11B v3 |
|---|---|---|---|---|
| ECE, real documents (lower = better) | 0.104 | 0.127 | 0.197 | 0.142 |
| Median latency per document (all models on the same computer) | 0.05 s | 0.28 s | 1.75 s | 3.01 s |

Models compared: [Jerzyk 1.0](https://huggingface.co/trenify/jerzyk-1.0) (calibrated); [basal-2.0-mini](https://huggingface.co/Remek/basal-2.0-mini-MLX-8bit) (MLX 8-bit, native `/v1/systemone`); [Qwen3 8B](https://huggingface.co/Qwen/Qwen3-8B-GGUF) and [Bielik 11B v3.0 Instruct](https://huggingface.co/speakleash/Bielik-11B-v3.0-Instruct-GGUF) (GGUF Q4_K_M in llama.cpp, zero-shot, answer chosen from option log-probabilities).

> **Note.** These results were measured on the benchmark text before anonymisation of the real documents (names of judges, officials and private persons replaced with placeholders such as `[SĘDZIA]` and `[OSOBA]`). On the published, anonymised text Jerzyk 1.0 scores 85.5% instead of 85.8% on real documents. The other models will be re-measured on the published text in a later update.

How to read the table:

- **Jerzyk is best on average**, both on generated and on real documents, and is 5–60× faster than the other models.
- **Where it wins:** urgency (the rules follow 7/14-day thresholds in [`docs/SPEC.md`](docs/SPEC.md)), deadlines in court letters, routing questions (e-mail department, cost category) and calibration (ECE).
- **Where larger models win:** document type of generated court letters, and deadlines in real administrative notices (Bielik). On the document type of real notices Jerzyk and Bielik are equal.
- **Known weakness: deadlines in long real administrative notices** (Jerzyk 73%, Bielik 82%). Always use Jerzyk together with `jerzyk.deadlines` (rule-based deadline extraction), and route low-confidence answers to a person.
- **jerzyk-bench was built by the authors of Jerzyk.** To keep the comparison checkable, the test split was never used for training or calibration, every model was run with the same questions and scoring (`scripts/evaluate.py`), and the benchmark and evaluation code are public, so anyone can re-run it.
- Jerzyk is trained on the conventions in `docs/SPEC.md`. The other models see them for the first time (zero-shot), so the urgency comparison is not fully apples to apples.
- The generated test documents were written by Bielik 11B (court, administrative, accounting) and Claude (e-mails). Jerzyk's training data was written by a different model (Qwen3 8B) and comes from real documents from other offices.
- The real documents (court rulings from SAOS, public notices from samorzad.gov.pl) never overlap with training data. Notices in the test come from offices that do not appear in training.
- 31 court-ruling fragments that start mid-text, with no "WYROK"/"POSTANOWIENIE" header, are reported separately (`sad_real_fragmenty_test`). Jerzyk 1.0 scores 80.6% on them.

## What is in this repository

| Path | Purpose |
|---|---|
| `jerzyk/` | The package. `model.py` (the `Jerzyk` class, calibration), `questions.py` (ready-made questions and answer options), `deadlines.py` (Polish deadline rules: KC/KPC/KPA, Saturdays, holidays incl. Christmas Eve from 2025), `serve.py` (HTTP server: `/v1/systemone`, `/api/demo`), `demo/` (demo page) |
| `scripts/` | Data and evaluation tools, grouped by purpose (run from the repository root as `python -m scripts.<name>`) |
| `scripts/` — benchmark | `generate_benchmark.py` (generated test and dev sets: labels by construction from recipes), `check_benchmark.py` (automatic checks), `review_benchmark.py` (manual review in the terminal) |
| `scripts/` — real documents | `fetch_saos.py`, `build_saos_dev.py` (SAOS court rulings), `fetch_legal_sources.py` (legal texts), `collect_notice_urls.py`, `fetch_notices.py`, `notices_training_data.py` (public notices from samorzad.gov.pl), `anonymize_rulings.py` (anonymisation before publication) |
| `scripts/` — training | `generate_training_data.py` (generate, check and build the training data), `calibrate.py` (temperature calibration on dev), `train.sh` (the training pipeline) |
| `scripts/` — evaluation | `evaluate.py` (any model: Jerzyk, `systemone` servers, LLMs via llama.cpp), `evaluate_model.sh`, `evaluate_basal.sh`, `evaluate_published.sh`, `results_table.py` (results tables), `llm.py` (shared LLM helpers) |
| `scripts/` — release | `build_release.py` (prepares the published version of the benchmark) |
| `tests/` | Unit tests of the calibration, the API, the server, the questions, the deadlines and the scripts (no model needed) |
| `docs/` | `SPEC.md`: jerzyk-bench specification, questions, answer options, labelling rules and all decisions taken. `TRAINING.md`: how to reproduce or improve the model on a Mac, an NVIDIA GPU or in the cloud |

## How it was built

1. **Specification first.** [`docs/SPEC.md`](docs/SPEC.md) defines every question and the labelling rules. For example: an invoice payment term is not a "deadline"; urgency 3 means ≤ 7 days; a threat of court in an e-mail means the customer is upset.
2. **Labels by construction.** The generator gets a recipe (document type, deadline, urgency) and writes a document that matches it. Automatic checks and a second model reject documents that drift from the recipe.
3. **Real documents.** About 500 court rulings from SAOS with document type from metadata, and 84 public notices from municipal and county offices, with deadline and urgency from rules. The rules agree with manual labels in 91% of cases.
4. **Fine-tuning** of [Laya multilingual](https://huggingface.co/convaiinnovations/laya-multilingual) (322M, mmBERT encoder) for 4 epochs.
5. **Calibration.** One temperature per question type, fitted on the dev split, never on the test split.

No training data comes from closed-model APIs. Generators and filters are open-weight Apache-2.0 models (Qwen3, Bielik), plus official documents.

## Limitations

- Polish documents only. Input is truncated to about 1024 tokens (about 3,000 characters), so a deadline at the end of a long notice may be missed.
- Not legal advice. Jerzyk helps sort and prioritise correspondence. A person must check deadlines and decisions with consequences, especially low-confidence ones.
- The real-document test set is small (145 documents). The 56 administrative notices were labelled by Claude following `docs/SPEC.md`, then checked by two independent blind re-labellings and a rule check, with disagreements adjudicated against the SPEC (11 notices corrected, 2026-10-19). They have not been reviewed by a human annotator.
- Urgency follows the conventions in `docs/SPEC.md`. Your organisation may need different thresholds, so retrain on your own data as described in [`docs/TRAINING.md`](docs/TRAINING.md).

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
