# jerzyk-bench — specyfikacja v0.2 (zaakceptowana 2026-10-16)

Polski benchmark modeli decyzyjnych: tekst + pytanie z zamkniętą listą odpowiedzi → wybór z prawdopodobieństwem.
Typy pytań jak w Jev / llama.cpp `/v1/systemone`: `choice`, `noul` (tak/nie), `score` (skala).

## Zasady wspólne

- **Perspektywa:** pismo trafiło do organizacji, która używa systemu (kancelaria, pracownia, biuro, firma).
  „Adresat” = ta organizacja lub jej klient, którego reprezentuje.
- **Odpowiedź wzorcowa** wynika z treści pisma. Gdy treść nie wystarcza, poprawna odpowiedź to `inne` / `nie` / najniższy poziom — nie zgadujemy kontekstu.
- **Dane:** zbiór testowy przeglądany w 100% przez człowieka, nigdy nie używany do treningu.
  Źródła: generowane (Bielik, Apache 2.0) + prawdziwe orzeczenia z SAOS (dokumenty urzędowe, poza prawem autorskim, art. 4 pr. aut.). Wszystkie dane osobowe fikcyjne lub zanonimizowane.

### Pytanie wspólne: `termin` (noul)
> Czy pismo wymaga od adresata podjęcia czynności w określonym czasie albo otwiera mu taki termin?

**TAK**, gdy pismo:
1. wyznacza termin na czynność adresata (zapłata, uzupełnienie braków, odpowiedź, złożenie dokumentu),
2. jest orzeczeniem/decyzją, od której adresatowi przysługuje środek zaskarżenia z terminem (apelacja, zażalenie, odwołanie, sprzeciw, zarzuty, skarga),
3. wyznacza datę stawiennictwa (rozprawa, posiedzenie, przesłuchanie, oględziny),
4. jest wezwaniem do zapłaty z terminem.

**NIE**, gdy pismo jest informacyjne, jest pismem strony przeciwnej bez wezwania sądu/organu, fakturą z samym terminem płatności (rutyna księgowa, nie termin procesowy/urzędowy), albo nie da się z niego ustalić żadnej czynności adresata.

### Pytanie wspólne: `pilnosc` (score, 4 poziomy) — liczona z terminu, nie z „wrażenia”
| poziom | kiedy |
|---|---|
| 0 niska | brak czynności do wykonania (informacja, kopia do wiadomości, reklama) |
| 1 średnia | czynność bez terminu albo termin dłuższy niż 14 dni |
| 2 wysoka | termin 8–14 dni |
| 3 krytyczna | termin do 7 dni włącznie albo termin już minął / „niezwłocznie” |

Doprecyzowania:
- odpis pisma strony przeciwnej bez wezwania sądu/organu → `termin` NIE, `pilnosc` 1 (trzeba przeczytać i ocenić),
- w dziedzinie `ksieg` dokument do zaksięgowania (faktura, paragon, wyciąg, umowa) → `pilnosc` 1,
- data rozprawy, oględzin lub posiedzenia liczona od daty pisma,
- uprawnienie z terminem (np. „uwagi można składać w terminie 14 dni”) to też `termin` TAK — pismo otwiera adresatowi termin, tak jak przy środku zaskarżenia.

Termin liczony od doręczenia, gdy pismo tak mówi („w terminie 7 dni od doręczenia” → 3).
Termin ustawowy niewpisany w pismo (np. 14 dni na apelację od doręczenia wyroku z uzasadnieniem) liczy się tylko, gdy pismo go wskazuje albo jest to oczywiste z pouczenia.

## Dziedziny

### A. `sad` — pisma sądowe (kancelarie, komornicy, windykacja)
`rodzaj` (choice):
| opcja | opis |
|---|---|
| wyrok | wyrok sądu (każdej instancji) |
| postanowienie | postanowienie sądu lub referendarza |
| nakaz_zaplaty | nakaz zapłaty (upominawczy, nakazowy, EPU) |
| wezwanie_sadu | wezwanie / zobowiązanie / zarządzenie nakładające obowiązek (braki, opłata, odpowiedź na pozew) |
| zawiadomienie_o_terminie | zawiadomienie lub wezwanie na rozprawę / posiedzenie |
| pismo_wszczynajace | pozew, wniosek, akt oskarżenia — od strony |
| pismo_strony | odpowiedź na pozew, apelacja, zażalenie, pismo przygotowawcze — od strony |
| inne | korespondencja niesądowa |

+ `termin`, `pilnosc`

### B. `adm` — pisma administracyjne (architekci, każda firma z e-Doręczeniami)
`rodzaj` (choice):
| opcja | opis |
|---|---|
| decyzja | decyzja administracyjna (WZ, pozwolenie na budowę, inna) |
| postanowienie | postanowienie organu (np. uzgodnienie w trybie KPA, odmowa wszczęcia) |
| wezwanie_do_uzupelnienia | wezwanie do usunięcia braków / uzupełnienia dokumentów / wyjaśnień |
| zawiadomienie | zawiadomienie lub obwieszczenie o wszczęciu, o zebraniu materiału, **o wydaniu decyzji** (to nie sama decyzja), o przedłużeniu terminu, o oględzinach |
| sprzeciw_zgloszenia | sprzeciw do zgłoszenia robót lub informacja o braku sprzeciwu |
| uzgodnienie_opinia | uzgodnienie / opinia / warunki od gestora sieci, konserwatora, zarządcy drogi, rzeczoznawcy |
| korespondencja_projektowa | pismo lub e-mail inwestora, wykonawcy, projektanta branżowego |
| inne | faktury, reklamy, informacje ogólne |

+ `termin`, `pilnosc`

### C. `ksieg` — dokumenty księgowe i finansowe (biura rachunkowe, działy finansowe)
`rodzaj` (choice): faktura · faktura_korygujaca · paragon · nota · wyciag_bankowy · umowa · pismo_us (urząd skarbowy, KAS) · pismo_zus · wezwanie_do_zaplaty · inne

`kategoria_kosztu` (choice, tylko dla faktur i paragonów): towary_handlowe · materialy · uslugi_obce · media_i_telekomunikacja · paliwo_i_samochod · najem · szkolenia · reprezentacja · srodek_trwaly · nie_dotyczy

+ `termin`, `pilnosc`

### D. `email` — wiadomości od klientów (każda firma usługowa / sklep)
`dzial` (choice): sprzedaz · zamowienia_i_dostawy · reklamacje_i_zwroty · platnosci_i_faktury · wsparcie_techniczne · inne
- Problem z doręczeniem (opóźnienie, „doręczono”, a paczki nie ma, zmiana adresu) = zamowienia_i_dostawy; wada, uszkodzenie, zły produkt, zwrot = reklamacje_i_zwroty.

`rezygnacja` (noul): Czy klient chce zrezygnować, wypowiedzieć umowę lub zamknąć konto?
- TAK tylko przy końcu relacji: wypowiedzenie usługi/abonamentu/umowy, zamknięcie konta, „nie będę już u Państwa kupować”.
- NIE przy zwrocie lub odstąpieniu od pojedynczego zakupu (zwrot w 14 dni, wymiana) — to sprawa działu reklamacji i zwrotów.

`zdenerwowany` (noul): Czy klient wyraża wyraźne niezadowolenie lub złość?
- Groźba sądu, mediów, rzecznika konsumentów lub publicznej skargi = TAK, nawet przy uprzejmym tonie.

`pilnosc` (score) — dla e-maili własna skala:
| poziom | kiedy |
|---|---|
| 0 niska | pytanie ogólne, podziękowanie, informacja |
| 1 średnia | sprawa do załatwienia, nic nie jest zablokowane |
| 2 wysoka | klient jest zablokowany (nie może zamówić, zapłacić, użyć usługi) |
| 3 krytyczna | trwająca szkoda lub przestój, bezpieczeństwo, groźba sądu/mediów, termin dziś |

Doprecyzowanie (v3, 2026-10-18): poziom wynika z treści, nie z tematu. „Pobrano dwa razy” bez pośpiechu = 1; ta sama sprawa z zapowiedzią sądu = 3. Brak możliwości zalogowania / zapłaty / odbioru = 2. Generator dostaje scenariusz z dozwolonymi poziomami (`gen_bench.SCENARIUSZE_EMAIL`) i zdanie, które musi wynikać z treści (`WSKAZOWKI_PILNOSCI`). E-maile z v1/v2 (losowa pilność) przeniesione do `data/odrzucone/email-v1/`.

## Rozmiar i podział

| zbiór | na dziedzinę | razem | użycie |
|---|---|---|---|
| test | 120 | 480 | tylko ocena, przegląd ręczny 100% |
| dev | 30 | 120 | kalibracja i dobór progów |
| train | 1 000–2 000 | 4 000–8 000 | trening Jerzyka, etykiety od Bielika, przegląd próbki |

Train generowany innymi szablonami tematów niż test, żeby nie uczyć się „na pamięć” ich stylu.

## Metryki

- `choice`: trafność, macro-F1
- `noul`: trafność (próg 0,5), Brier
- `score`: trafność dokładna, trafność ±1, MAE wartości oczekiwanej
- **kalibracja:** ECE (15 przedziałów) dla wszystkich pytań razem i per typ
- **szybkość:** mediana i p95 ms na dokument (wszystkie pytania), sprzęt podany
- **koszt:** $ / 1000 dokumentów (API) albo „lokalnie”
- wynik główny: średnia trafności po dziedzinach + ECE obok (nie łączymy w jedną liczbę)

## Decyzje
- 2026-10-16: termin płatności faktury nie jest `termin`; progi pilności 7 / 14 dni; cztery dziedziny bez zmian.


## Decyzje (2026-10-18)
- Zatwierdzone reguły e-maili: zwrot ≠ rezygnacja; groźba sądu/mediów ⇒ zdenerwowany; doręczenie ⇒ dostawy, wada ⇒ reklamacje. Etykiety testu/dev e-maili zaktualizowane (`gen_bench.reguly_email`).
- Prawdziwy test orzeczeń: 31/120 pism to fragmenty uzasadnienia bez nagłówka (WYROK/POSTANOWIENIE w pierwszych 400 znakach) — rodzaj nierozstrzygalny z treści (Bielik 6,5%). Przeniesione do `sad_real_fragmenty_test.jsonl` (raportowane osobno, poza średnią); główny `sad_real_test.jsonl` = 89 pism z nagłówkiem. Reguła obiektywna, ta sama dla wszystkich modeli; oryginał w `data/odrzucone/real-test-v1/`.
- Prawdziwy test urzędowy v2: 56 pism z 9+ urzędów (bip_zbierz.py + bip.py, deduplikacja szablonów), etykiety: Claude według SPEC (do przeglądu użytkownika). Konwencje użyte przy etykietach: „doręczenie uważa się za dokonane po 14 dniach” nie jest terminem; pilność liczona od daty pisma (długość terminu), nie od dziś; uwagi „do czasu wydania decyzji” bez daty = brak terminu. Stary zbiór (30, ~18 szablonów) w `data/odrzucone/real-test-v1/`.
- Decyzje użytkownika (2026-10-18): pilność liczona od daty pisma (nie od dziś — wynik testu nie zmienia się w czasie); prawo sprzeciwu z terminem w obwieszczeniach o polowaniach = termin TAK.
