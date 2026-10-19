"""Domains of jerzyk-bench (docs/SPEC.md): the questions the model answers and the recipes for generated documents.

Question names, instructions and answer options are Polish on purpose: the model was trained on exactly these
texts, so they must not be translated or edited (tests/test_questions.py guards them).

A recipe is (document type, variant for the generator, deadline running, urgency). The generator writes a document
that contains the variant, so the gold answer is known by construction; a person only checks that the document
matches its recipe.
"""
import copy
from typing import Any, Dict

DEADLINE_QUESTION = ("Czy pismo wymaga od adresata podjęcia czynności w określonym czasie albo otwiera mu taki termin "
                     "(zapłata, uzupełnienie, odpowiedź, środek zaskarżenia, stawiennictwo)?")
URGENCY_LETTER = [
    "niska – nic nie trzeba robić",
    "średnia – trzeba coś zrobić, ale bez terminu albo termin dłuższy niż 14 dni",
    "wysoka – termin od 8 do 14 dni",
    "krytyczna – termin do 7 dni, niezwłocznie albo już minął",
]
URGENCY_EMAIL = [
    "niska – pytanie ogólne, podziękowanie, informacja",
    "średnia – sprawa do załatwienia, nic nie jest zablokowane",
    "wysoka – klient jest zablokowany (nie może zamówić, zapłacić, skorzystać z usługi)",
    "krytyczna – trwająca szkoda lub przestój, bezpieczeństwo, groźba sądu lub mediów, termin dziś",
]


def _choice(instructions, options):
    return {"type": "choice", "instructions": instructions, "criteria": options}


def _letter_common():
    return {
        "termin": {"type": "noul", "instructions": DEADLINE_QUESTION},
        "pilnosc": {"type": "score", "instructions": "Jak pilne jest to pismo?", "criteria": URGENCY_LETTER},
    }


# document types per domain: sad = court, adm = administrative, ksieg = accounting
DOCUMENT_TYPES = {
    "sad": {
        "wyrok": "wyrok sądu (każdej instancji)",
        "postanowienie": "postanowienie sądu lub referendarza",
        "nakaz_zaplaty": "nakaz zapłaty (upominawczy, nakazowy, EPU)",
        "wezwanie_sadu": "wezwanie, zobowiązanie lub zarządzenie sądu nakładające obowiązek",
        "zawiadomienie_o_terminie": "zawiadomienie lub wezwanie na rozprawę albo posiedzenie",
        "pismo_wszczynajace": "pozew, wniosek lub akt oskarżenia złożony przez stronę",
        "pismo_strony": "odpowiedź na pozew, apelacja, zażalenie lub pismo przygotowawcze strony",
        "inne": "korespondencja niesądowa",
    },
    "adm": {
        "decyzja": "decyzja administracyjna (warunki zabudowy, pozwolenie na budowę, inna)",
        "postanowienie": "postanowienie organu administracji",
        "wezwanie_do_uzupelnienia": "wezwanie do usunięcia braków, uzupełnienia dokumentów lub wyjaśnień",
        "zawiadomienie": "zawiadomienie lub obwieszczenie o wszczęciu, zebraniu materiału, wydaniu decyzji, przedłużeniu terminu lub oględzinach",
        "sprzeciw_zgloszenia": "sprzeciw do zgłoszenia robót albo informacja o braku sprzeciwu",
        "uzgodnienie_opinia": "uzgodnienie, opinia lub warunki od gestora sieci, konserwatora, zarządcy drogi, rzeczoznawcy",
        "korespondencja_projektowa": "pismo lub e-mail inwestora, wykonawcy albo projektanta branżowego",
        "inne": "faktury, reklamy, informacje ogólne",
    },
    "ksieg": {
        "faktura": "faktura VAT lub rachunek",
        "faktura_korygujaca": "faktura korygująca",
        "paragon": "paragon fiskalny",
        "nota": "nota księgowa lub obciążeniowa",
        "wyciag_bankowy": "wyciąg bankowy",
        "umowa": "umowa lub aneks",
        "pismo_us": "pismo z urzędu skarbowego lub KAS",
        "pismo_zus": "pismo z ZUS",
        "wezwanie_do_zaplaty": "wezwanie do zapłaty od kontrahenta",
        "inne": "inna korespondencja",
    },
}
COST_CATEGORIES = {
    "towary_handlowe": "towary do dalszej odsprzedaży",
    "materialy": "materiały i surowce",
    "uslugi_obce": "usługi obce (doradztwo, IT, sprzątanie, transport)",
    "media_i_telekomunikacja": "energia, woda, telefon, internet",
    "paliwo_i_samochod": "paliwo, serwis i eksploatacja samochodu",
    "najem": "najem lub dzierżawa",
    "szkolenia": "szkolenia i konferencje",
    "reprezentacja": "reprezentacja (catering, upominki dla kontrahentów)",
    "srodek_trwaly": "środek trwały (sprzęt, maszyny powyżej progu)",
    "nie_dotyczy": "dokument nie jest kosztem",
}
DEPARTMENTS = {  # customer e-mail routing
    "sprzedaz": "pytania o ofertę, ceny, dostępność",
    "zamowienia_i_dostawy": "status zamówienia, dostawa, zmiana zamówienia",
    "reklamacje_i_zwroty": "reklamacje, zwroty, wadliwy produkt",
    "platnosci_i_faktury": "płatności, faktury, rozliczenia",
    "wsparcie_techniczne": "problemy z działaniem usługi lub produktu",
    "inne": "inne sprawy",
}


def questions(domain: str) -> Dict[str, Dict[str, Any]]:
    """Ready-made questions of a domain (sad, adm, ksieg, email) in the TypeSafe Jev systemone format.

    Returns a new copy each time, so callers may change it without affecting later calls."""
    return copy.deepcopy(_questions(domain))


def _questions(domain):
    if domain == "email":
        return {
            "dzial": _choice("Do którego działu powinna trafić wiadomość?", DEPARTMENTS),
            "rezygnacja": {"type": "noul", "instructions": "Czy klient chce zrezygnować, wypowiedzieć umowę lub zamknąć konto?"},
            "zdenerwowany": {"type": "noul", "instructions": "Czy klient wyraża wyraźne niezadowolenie lub złość?"},
            "pilnosc": {"type": "score", "instructions": "Jak pilna jest wiadomość?", "criteria": URGENCY_EMAIL},
        }
    q = {"rodzaj": _choice("Jaki to rodzaj dokumentu?", DOCUMENT_TYPES[domain])}
    if domain == "ksieg":
        q["kategoria_kosztu"] = _choice("Do jakiej kategorii kosztu należy dokument?", COST_CATEGORIES)
    return {**q, **_letter_common()}


# (document type, variant, deadline running, urgency); the variants are Polish instructions for the generator.
# {d3} {d5} {d10} {d40} = letter date + N days, filled in when generating.
RECIPES = {
    "sad": [
        ("wyrok", "z pouczeniem, że apelację wnosi się w terminie 14 dni od doręczenia wyroku z uzasadnieniem", True, 2),
        ("wyrok", "wyrok sądu drugiej instancji, prawomocny, bez pouczenia o środkach zaskarżenia", False, 0),
        ("postanowienie", "z pouczeniem o zażaleniu w terminie tygodnia od doręczenia", True, 3),
        ("postanowienie", "z pouczeniem o skardze na orzeczenie referendarza w terminie 7 dni", True, 3),
        ("postanowienie", "postanowienie dowodowe, niezaskarżalne, doręczane do wiadomości", False, 0),
        ("nakaz_zaplaty", "z terminem dwóch tygodni na zapłatę albo wniesienie sprzeciwu lub zarzutów", True, 2),
        ("wezwanie_sadu", "z terminem 7 dni pod rygorem", True, 3),
        ("wezwanie_sadu", "z terminem 14 dni", True, 2),
        ("wezwanie_sadu", "z terminem 21 dni", True, 1),
        ("zawiadomienie_o_terminie", "rozprawa wyznaczona na {d40}", True, 1),
        ("zawiadomienie_o_terminie", "rozprawa wyznaczona na {d10}", True, 2),
        ("zawiadomienie_o_terminie", "posiedzenie wyznaczone na {d5}", True, 3),
        ("pismo_wszczynajace", "odpis pozwu lub wniosku doręczony bez wezwania sądu do zajęcia stanowiska", False, 1),
        ("pismo_strony", "odpis pisma strony przeciwnej doręczony bez wezwania sądu", False, 1),
        ("inne", "e-mail klienta z pytaniem o stan sprawy", False, 1),
        ("inne", "newsletter lub oferta wydawnictwa prawniczego", False, 0),
    ],
    "adm": [
        ("decyzja", "pozwolenie na budowę z pouczeniem o odwołaniu w terminie 14 dni od doręczenia", True, 2),
        ("decyzja", "decyzja o warunkach zabudowy z pouczeniem o odwołaniu w terminie 14 dni", True, 2),
        ("decyzja", "decyzja organu drugiej instancji z pouczeniem o skardze do WSA w terminie 30 dni", True, 1),
        ("postanowienie", "z pouczeniem o zażaleniu w terminie 7 dni", True, 3),
        ("postanowienie", "niezaskarżalne, doręczane do wiadomości", False, 0),
        ("wezwanie_do_uzupelnienia", "uzupełnienie dokumentów w terminie 7 dni pod rygorem pozostawienia bez rozpoznania", True, 3),
        ("wezwanie_do_uzupelnienia", "złożenie wyjaśnień w terminie 14 dni", True, 2),
        ("wezwanie_do_uzupelnienia", "usunięcie nieprawidłowości w projekcie w terminie 30 dni", True, 1),
        ("zawiadomienie", "o zebraniu materiału dowodowego i prawie wypowiedzenia się w terminie 7 dni", True, 3),
        ("zawiadomienie", "o oględzinach nieruchomości wyznaczonych na {d10}", True, 2),
        ("zawiadomienie", "o przedłużeniu terminu załatwienia sprawy", False, 0),
        ("zawiadomienie", "o wszczęciu postępowania, bez wzywania do działania", False, 0),
        ("sprzeciw_zgloszenia", "sprzeciw do zgłoszenia robót z pouczeniem o odwołaniu w terminie 14 dni", True, 2),
        ("sprzeciw_zgloszenia", "zaświadczenie o braku podstaw do wniesienia sprzeciwu", False, 0),
        ("uzgodnienie_opinia", "warunki przyłączenia do sieci ważne dwa lata, bez wymaganych działań", False, 0),
        ("uzgodnienie_opinia", "uzgodnienie z uwagami do uwzględnienia w projekcie, bez terminu", False, 1),
        ("korespondencja_projektowa", "inwestor prosi o zmianę w projekcie, bez terminu", False, 1),
        ("korespondencja_projektowa", "inwestor prosi o poprawki do {d3}", True, 3),
        ("korespondencja_projektowa", "wykonawca informuje o postępie prac", False, 0),
        ("inne", "faktura za oprogramowanie projektowe", False, 0),
        ("inne", "oferta szkolenia lub reklama", False, 0),
    ],
    "ksieg": [
        ("faktura", "zwykła faktura zakupowa", False, 1),
        ("faktura_korygujaca", "korekta ceny lub ilości", False, 1),
        ("paragon", "paragon za drobny zakup", False, 1),
        ("nota", "nota obciążeniowa lub księgowa", False, 1),
        ("wyciag_bankowy", "wyciąg z kilkoma operacjami", False, 1),
        ("umowa", "umowa lub aneks do zaksięgowania", False, 1),
        ("pismo_us", "wezwanie do złożenia wyjaśnień w terminie 7 dni", True, 3),
        ("pismo_us", "wezwanie do przedłożenia dokumentów w terminie 14 dni", True, 2),
        ("pismo_us", "informacja o dokonaniu zwrotu VAT", False, 0),
        ("pismo_zus", "informacja o zaległości z wezwaniem do zapłaty w terminie 7 dni", True, 3),
        ("pismo_zus", "informacja o stanie konta płatnika, bez zaległości", False, 0),
        ("wezwanie_do_zaplaty", "zapłata w terminie 7 dni", True, 3),
        ("wezwanie_do_zaplaty", "zapłata w terminie 14 dni", True, 2),
        ("inne", "reklama programu księgowego", False, 0),
    ],
}
# accounting document types that are a cost (they get a real cost category)
COST_DOCUMENT_TYPES = {"faktura", "faktura_korygujaca", "paragon"}
