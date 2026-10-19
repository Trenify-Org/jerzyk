# jerzyk-bench — specification v0.2 (accepted 2026-10-16)

A Polish benchmark for decision models: text + a question with a closed list of answers → a choice with a probability.
Question types follow Jev / llama.cpp `/v1/systemone`: `choice`, `noul` (yes/no), `score` (scale).

## Common rules

- **Point of view:** the letter reached an organisation that uses the system (a law office, a workshop, an office, a company).
  "Recipient" = that organisation or its client, whom it represents.
- **The reference answer** follows from the content of the letter. When the content is not enough, the correct answer is `inne` / `nie` / the lowest level. We do not guess the context.
- **Data:** the test set is reviewed 100% by a human and is never used for training.
  Sources: generated documents (Bielik, Apache 2.0) and real court rulings from SAOS (official documents, outside copyright under art. 4 of the Polish Copyright Act). All personal data is fictitious or anonymised.

### Common question: `termin` (deadline running?) (noul)
> Does the letter require the recipient to act within a set time, or does it open such a deadline for them?

**YES** when the letter:
1. sets a deadline for an action by the recipient (payment, supplementing missing items, a reply, filing a document),
2. is a judgment or decision against which the recipient may file a remedy with a deadline (appeal, complaint (zażalenie), objection (odwołanie), opposition (sprzeciw), defences (zarzuty), complaint (skarga)),
3. sets a date for appearance (hearing, session, questioning, inspection),
4. is a demand for payment with a deadline.

**NO** when the letter is informational, is a letter from the opposing party without a summons from a court or authority, is an invoice with only a payment due date (routine accounting, not a procedural or official deadline), or no action by the recipient can be identified from it.

### Common question: `pilnosc` (urgency) (score, 4 levels) — counted from the deadline, not from a "feeling"
| level | when |
|---|---|
| 0 low | no action to take (information, copy for information, advertising) |
| 1 medium | an action with no deadline, or a deadline longer than 14 days |
| 2 high | a deadline of 8–14 days |
| 3 critical | a deadline of up to 7 days inclusive, or a deadline that has already passed / "immediately" (niezwłocznie, "without delay") |

Clarifications:
- a copy of a letter from the opposing party without a summons from a court or authority → `termin` NO, `pilnosc` 1 (it must be read and assessed),
- in the domain `ksieg`, a document to be booked (invoice, receipt, bank statement, contract) → `pilnosc` 1,
- the date of a hearing, inspection or session is counted from the date of the letter,
- a right with a deadline (e.g. "comments may be submitted within 14 days" (uwagi można składać w terminie 14 dni)) is also `termin` YES — the letter opens a deadline for the recipient, just as with a remedy.

A deadline is counted from delivery when the letter says so ("within 7 days of delivery" (w terminie 7 dni od doręczenia) → 3).
A statutory deadline that is not written into the letter (e.g. 14 days to appeal a judgment with its reasons, counted from delivery) counts only when the letter states it or when it is obvious from the notice of remedies.

## Domains

### A. `sad` — court letters (law offices, bailiffs, debt collection)
`rodzaj` (document type) (choice):
| option | description |
|---|---|
| wyrok | a court judgment (any instance) |
| postanowienie | a court or court-clerk (referendarz) decision |
| nakaz_zaplaty | a payment order (summary, default, or EPU electronic) |
| wezwanie_sadu | a summons / obligation / court order imposing a duty (missing items, a fee, a reply to a statement of claim) |
| zawiadomienie_o_terminie | a notice or summons to a hearing / session |
| pismo_wszczynajace | a statement of claim, a motion, an indictment — from a party |
| pismo_strony | a reply to a statement of claim, an appeal, a complaint (zażalenie), a preparatory submission — from a party |
| inne | non-court correspondence |

+ `termin`, `pilnosc`

### B. `adm` — administrative letters (architects, any company using e-Delivery)
`rodzaj` (document type) (choice):
| option | description |
|---|---|
| decyzja | an administrative decision (building-permit decision WZ, a building permit, other) |
| postanowienie | an authority's order (e.g. agreement under the administrative procedure code (KPA), refusal to open proceedings) |
| wezwanie_do_uzupelnienia | a request to remove defects / supplement documents / give explanations |
| zawiadomienie | a notice or public announcement of opening proceedings, of collecting evidence, **of issuing a decision** (this is not the decision itself), of extending a deadline, of an inspection |
| sprzeciw_zgloszenia | an objection to a notification of works, or information that no objection is raised |
| uzgodnienie_opinia | agreement / opinion / conditions from a network operator, a conservator, a road manager, an expert |
| korespondencja_projektowa | a letter or e-mail from the investor, the contractor, or a trade designer |
| inne | invoices, advertising, general information |

+ `termin`, `pilnosc`

### C. `ksieg` — accounting and financial documents (accounting firms, finance departments)
`rodzaj` (document type) (choice): faktura (invoice) · faktura_korygujaca (corrective invoice) · paragon (receipt) · nota (note) · wyciag_bankowy (bank statement) · umowa (contract) · pismo_us (letter from the tax office, KAS) · pismo_zus (letter from the social insurance office, ZUS) · wezwanie_do_zaplaty (demand for payment) · inne (other)

`kategoria_kosztu` (cost category) (choice, only for invoices and receipts): towary_handlowe (trade goods) · materialy (materials) · uslugi_obce (external services) · media_i_telekomunikacja (utilities and telecoms) · paliwo_i_samochod (fuel and car) · najem (rent) · szkolenia (training) · reprezentacja (entertainment) · srodek_trwaly (fixed asset) · nie_dotyczy (not applicable)

+ `termin`, `pilnosc`

### D. `email` — messages from customers (any service company / shop)
`dzial` (department) (choice): sprzedaz (sales) · zamowienia_i_dostawy (orders and deliveries) · reklamacje_i_zwroty (complaints and returns) · platnosci_i_faktury (payments and invoices) · wsparcie_techniczne (technical support) · inne (other)
- A delivery problem (delay, "delivered" but the parcel is missing, change of address) = zamowienia_i_dostawy; a defect, damage, wrong product, return = reklamacje_i_zwroty.

`rezygnacja` (cancellation) (noul): Does the customer want to cancel, terminate the contract, or close the account?
- YES only at the end of the relationship: terminating a service / subscription / contract, closing an account, "I will not buy from you any more".
- NO for a return or withdrawal from a single purchase (return within 14 days, exchange) — that is a matter for the complaints and returns department.

`zdenerwowany` (upset) (noul): Does the customer express clear dissatisfaction or anger?
- A threat of court, of the media, of a consumer ombudsman (rzecznik konsumentów) or of a public complaint = YES, even with a polite tone.

`pilnosc` (urgency) (score) — for e-mails, its own scale:
| level | when |
|---|---|
| 0 low | general question, thanks, information |
| 1 medium | a matter to resolve, nothing is blocked |
| 2 high | the customer is blocked (cannot order, pay, or use the service) |
| 3 critical | ongoing damage or downtime, safety, a threat of court / media, a deadline today |

Clarification (v3, 2026-10-18): the level follows from the content, not from the subject. "Downloaded twice" with no urgency = 1; the same matter with a warning of court action = 3. No way to log in / pay / collect = 2. The generator receives a scenario with the permitted levels (`scripts.generate_benchmark.EMAIL_SCENARIOS`) and a sentence that must follow from the text (`scripts.generate_benchmark.URGENCY_HINTS`). E-mails from v1/v2 (random urgency) were moved to `data/odrzucone/email-v1/`.

## Size and split

| set | per domain | total | use |
|---|---|---|---|
| test | 120 | 480 | evaluation only, 100% manual review |
| dev | 30 | 120 | calibration and choosing thresholds |
| train | 1,000–2,000 | 4,000–8,000 | training Jerzyk, labels from Bielik, review of a sample |

The train set is generated with different topic templates from the test set, so the model does not learn the style of the test "by heart".

## Metrics

- `choice`: accuracy, macro-F1
- `noul`: accuracy (threshold 0.5), Brier score
- `score`: exact accuracy, accuracy ±1, MAE of the expected value
- **calibration:** ECE (15 bins) for all questions together and per type
- **speed:** median and p95 ms per document (all questions), hardware stated
- **cost:** $ per 1,000 documents (API) or "local"
- main result: mean accuracy across domains, with ECE next to it (we do not combine them into one number)

## Decisions
- 2026-10-16: the payment due date on an invoice is not `termin`; urgency thresholds 7 / 14 days; four domains unchanged.


## Decisions (2026-10-18)
- Approved e-mail rules: a return ≠ cancellation; a threat of court / media ⇒ upset; delivery ⇒ deliveries, defect ⇒ complaints. The labels of the test/dev e-mails were updated (`scripts.generate_benchmark.email_rules`).
- Real test of rulings: 31 of 120 letters are fragments of reasoning without a heading (WYROK/POSTANOWIENIE, "JUDGMENT"/"DECISION", in the first 400 characters) — the document type cannot be decided from the text (Bielik 6.5%). Moved to `sad_real_fragmenty_test.jsonl` (reported separately, outside the average); the main `sad_real_test.jsonl` = 89 letters with a heading. An objective rule, the same for all models; the original is in `data/odrzucone/real-test-v1/`.
- Real official test v2: 56 letters from 9+ offices (`scripts/collect_notice_urls.py` + `scripts/fetch_notices.py`, template de-duplication), labels: Claude, according to SPEC (for the user's review). Conventions used for the labels: "delivery is deemed made after 14 days" (doręczenie uważa się za dokonane po 14 dniach) is not a deadline; urgency is counted from the date of the letter (the length of the deadline), not from today; remarks "until a decision is issued" (do czasu wydania decyzji) with no date = no deadline. The old set (30, ~18 templates) is in `data/odrzucone/real-test-v1/`.
- Decisions of the user (2026-10-18): urgency is counted from the date of the letter (not from today — the test result does not change over time); a right of objection with a deadline in hunting-notice announcements = `termin` YES.


## Decisions (2026-10-19)
- Label check of `adm_real_test` (56 notices): two independent blind re-labellings and a rule check, disagreements adjudicated against this SPEC; 11 notices corrected (`label_changes` in each row). Results on real documents were re-scored from the stored predictions (`scripts/rescore_results.py`), the models were not run again.
- A right to submit remarks or inspect the files with no deadline stated = an action without a deadline, `pilnosc` 1 (not 0).
- A notice of an issued decision with no deadline stated stays `pilnosc` 0.
- A text cut off before the appeal clause is labelled from what is visible.
- A procedural notice inside a proceeding (e.g. environmental impact assessment) = `zawiadomienie`; a general planning announcement = `inne`; an attachment = `inne`.
