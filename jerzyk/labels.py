"""English names of the ready-made questions and their answers.

The model was trained on Polish question texts and answer options (jerzyk.questions), and the option names are
part of what it reads: they stay Polish inside. Jerzyk.ask() translates the result afterwards, so the English
names do not change any prediction. The Polish names are what jerzyk-bench uses (ask(..., labels="pl")).
"""
from typing import Any, Dict, Tuple

QUESTION_NAMES = {
    "rodzaj": "document_type",
    "termin": "deadline",              # does the letter set or open a deadline for the addressee?
    "pilnosc": "urgency",              # 0 low … 3 critical
    "kategoria_kosztu": "cost_category",
    "dzial": "department",
    "rezygnacja": "cancellation",      # does the customer want to cancel or close the account?
    "zdenerwowany": "upset",           # is the customer clearly upset?
}

# (domain, question) → {Polish option: English name}; the same Polish word can mean different things per domain
ANSWER_NAMES = {
    ("sad", "rodzaj"): {
        "wyrok": "judgment", "postanowienie": "court_decision", "nakaz_zaplaty": "payment_order",
        "wezwanie_sadu": "court_summons", "zawiadomienie_o_terminie": "hearing_notice",
        "pismo_wszczynajace": "statement_of_claim", "pismo_strony": "party_letter", "inne": "other"},
    ("adm", "rodzaj"): {
        "decyzja": "decision", "postanowienie": "procedural_decision",
        "wezwanie_do_uzupelnienia": "request_to_complete", "zawiadomienie": "notice",
        "sprzeciw_zgloszenia": "objection_to_notification", "uzgodnienie_opinia": "agreement_or_opinion",
        "korespondencja_projektowa": "project_correspondence", "inne": "other"},
    ("ksieg", "rodzaj"): {
        "faktura": "invoice", "faktura_korygujaca": "corrective_invoice", "paragon": "receipt",
        "nota": "accounting_note", "wyciag_bankowy": "bank_statement", "umowa": "contract",
        "pismo_us": "tax_office_letter", "pismo_zus": "social_insurance_letter",
        "wezwanie_do_zaplaty": "payment_demand", "inne": "other"},
    ("ksieg", "kategoria_kosztu"): {
        "towary_handlowe": "goods_for_resale", "materialy": "materials", "uslugi_obce": "external_services",
        "media_i_telekomunikacja": "utilities_and_telecom", "paliwo_i_samochod": "fuel_and_car", "najem": "rent",
        "szkolenia": "training", "reprezentacja": "entertainment", "srodek_trwaly": "fixed_asset",
        "nie_dotyczy": "not_applicable"},
    ("email", "dzial"): {
        "sprzedaz": "sales", "zamowienia_i_dostawy": "orders_and_deliveries",
        "reklamacje_i_zwroty": "complaints_and_returns", "platnosci_i_faktury": "payments_and_invoices",
        "wsparcie_techniczne": "technical_support", "inne": "other"},
}


def to_english(answers: Dict[str, Tuple[Any, float]], domain: str) -> Dict[str, Tuple[Any, float]]:
    """{question: (answer, confidence)} with English names; questions without a translation pass through."""
    out = {}
    for qid, (answer, confidence) in answers.items():
        names = ANSWER_NAMES.get((domain, qid), {})
        out[QUESTION_NAMES.get(qid, qid)] = (names.get(answer, answer), confidence)
    return out
