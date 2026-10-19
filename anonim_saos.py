"""Zamienia nazwiska sędziów i protokolantów w prawdziwych orzeczeniach jerzyk-bench przed publikacją.

  python3 anonim_saos.py     # → wydanie/anonimizacja/{sad_real_test,sad_real_fragmenty_test,sad_real_dev}.jsonl

SAOS anonimizuje strony, ale publikuje skład sądu. Na prośbę autora projektu zamieniamy:
- sędziów (metadane SAOS `judges`) → [SĘDZIA], protokolantów (`courtReporters`) → [PROTOKOLANT],
  także w formie „R. Troll” i samym nazwiskiem,
- na wszelki wypadek imię i nazwisko po słowach „Sędzia/SSR/SSO/SSA/Ławnik/Protokolant/Prokurator/referendarz”,
- imię z listy częstych imion (także w odmianie: „Urszuli”, „Zdzisława”) z następującym nazwiskiem.
Metadane bierzemy z lokalnego zrzutu SAOS (data/prawo/saos-od-*, prawo.py).
"""
import glob
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "wydanie" / "anonimizacja"
PLIKI = ["sad_real_test", "sad_real_fragmenty_test", "sad_real_dev"]
DUZA = r"(?!Protokolant|Przewodnicz|Sędzi|Ławni|Prokurator)[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+"
ROLE = re.compile(rf"((?:[Ss]ędzi(?:a|owie|ego|emu|ą|ów|ami)?|SSR|SSO|SSA|SR|SO|SA|[Łł]awni(?:k|cy)|[Pp]rotokolant(?:ka)?|[Pp]rokurator|"
                  rf"[Rr]eferendarz(?:\s+sądowy)?|[Ss]ekretarz\s+sądowy|[Aa]systent\s+sędziego|[Aa]sesor\s+sądowy|stażysta)"
                  rf"[\s:–\-.,()a-ząćęłńóśźżA-Z]{{0,40}}?)"
                  rf"\b({DUZA}(?:\s*-\s*{DUZA}|\s+{DUZA}){{0,2}})\b(?!\.)")
# Ostatnia siatka: pełne „Imię Nazwisko” z częstych imion (strony SAOS już ma jako inicjały) — w składzie [SĘDZIA], dalej [OSOBA].
IMIONA = ("Anna Maria Katarzyna Małgorzata Agnieszka Barbara Ewa Krystyna Elżbieta Magdalena Joanna Aleksandra Monika Beata "
          "Dorota Renata Iwona Jolanta Marta Justyna Urszula Karolina Dominika Agata Izabela Grażyna Halina Sylwia Edyta "
          "Paulina Ilona Teresa Danuta Bożena Alicja Natalia Kinga Emilia Lidia Wioletta Marzena Ewelina Zofia Hanna "
          "Piotr Krzysztof Andrzej Tomasz Paweł Jan Michał Marcin Marek Grzegorz Józef Łukasz Adam Zbigniew Jerzy Tadeusz "
          "Mariusz Dariusz Rafał Mirosław Wojciech Robert Jacek Janusz Maciej Sławomir Jarosław Kamil Wiesław Roman Damian "
          "Przemysław Stanisław Artur Bartosz Sebastian Mateusz Daniel Arkadiusz Ryszard Waldemar Leszek Bogdan Henryk "
          "Kazimierz Zdzisław Edward Witold Ireneusz Cezary Radosław Szymon Jakub Konrad Filip Dawid Norbert").split()


def odmiany(imie):
    """Imię w przypadkach zależnych (dopełniacz, celownik, biernik, narzędnik, miejscownik) — przybliżenie."""
    if imie.endswith("ia"):          # Maria → Marii, Marię, Marią
        return {imie, imie[:-1] + "i", imie[:-1] + "ę", imie[:-1] + "ą"}
    if imie.endswith(("la", "ja")):  # Urszula → Urszuli, Urszulę; Kinga ↓
        return {imie, imie[:-1] + "i", imie[:-1] + "ę", imie[:-1] + "ą"}
    if imie.endswith("a"):           # Anna → Anny, Annie, Annę; Kinga → Kingi
        rdzen = imie[:-1]
        return {imie, rdzen + "y", rdzen + "i", rdzen + "ie", rdzen + "ę", rdzen + "ą"}
    if imie.endswith("ek"):          # Marek → Marka, Markowi
        rdzen = imie[:-2] + "k"
        return {imie, rdzen + "a", rdzen + "owi", rdzen + "iem", rdzen + "u"}
    return {imie, imie + "a", imie + "owi", imie + "em", imie + "ie", imie + "u"}  # Zdzisław → Zdzisława


WSZYSTKIE_IMIONA = sorted({o for i in IMIONA for o in odmiany(i)}, key=len, reverse=True)
PELNE = re.compile(rf"\b(?:{'|'.join(WSZYSTKIE_IMIONA)})\s+{DUZA}(?:\s*-\s*{DUZA})?\b")
# Imię zostające przed znacznikiem albo przed „...” (ucięty tekst) w składzie sądu.
RESZTA = re.compile(rf"\b{DUZA}\s+(\[(?:SĘDZIA|PROTOKOLANT|OSOBA)\])")


def zamien(tekst, osoby, znacznik):
    for o in sorted(osoby, key=len, reverse=True):
        czesci = o.split()
        if len(czesci) < 2:
            continue
        imie, nazwisko = czesci[0], czesci[-1]
        wzor = r"\s*-\s*".join(re.escape(x) for x in o.replace(" - ", "-").split("-"))
        tekst = re.sub(rf"\b{wzor}\b", znacznik, tekst)
        tekst = re.sub(rf"\b{re.escape(imie)}\b(?=\s*(?:\.\.\.|\[|$))", znacznik, tekst)
        tekst = re.sub(rf"\b{re.escape(imie[0])}\.\s*{re.escape(nazwisko)}\b", znacznik, tekst)
        for czesc in re.split(r"[\s\-–]+", o):  # każda część nazwiska złożonego, także w odmianie
            if len(czesc) > 3:
                tekst = re.sub(rf"\b{re.escape(czesc)}\w{{0,3}}\b", znacznik, tekst)
        tekst = re.sub(rf"({re.escape(znacznik)})(?:\s*[–\-]\s*{re.escape(znacznik)})+", r"\1", tekst)
    return tekst


def anonimizuj(tekst, sedziowie=(), protokolanci=()):
    """Tekst orzeczenia bez imion i nazwisk składu, prokuratorów i protokolantów."""
    t = zamien(tekst, sedziowie, "[SĘDZIA]")
    t = zamien(t, protokolanci, "[PROTOKOLANT]")
    t = ROLE.sub(lambda m: m.group(1) + ("[OSOBA]" if not m.group(2).startswith("[") else m.group(2)), t)
    t = RESZTA.sub(r"\1", t)
    t = re.sub(rf"(\[(?:SĘDZIA|OSOBA|PROTOKOLANT)\])\s*[–\-]\s*{DUZA}", r"\1", t)  # „[OSOBA] – Kuchta”
    t = re.sub(rf"(\[(?:SĘDZIA|OSOBA)\])\s+{DUZA}\s+{DUZA}\b(?!\s+(?:Sąd|Wydział))", r"\1 [SĘDZIA]", t)  # kolejny członek składu
    return PELNE.sub("[SĘDZIA]", t[:1200]) + PELNE.sub("[OSOBA]", t[1200:])


def main():
    meta = {}
    for f in glob.glob(str(ROOT / "data/prawo/saos-od-*/*.jsonl.gz")):
        for l in gzip.open(f, "rt", encoding="utf-8"):
            j = json.loads(l)
            meta[j["id"]] = ([x["name"] for x in j.get("judges", [])], j.get("courtReporters", []))
    OUT.mkdir(parents=True, exist_ok=True)
    for plik in PLIKI:
        rows = [json.loads(l) for l in (ROOT / "data/bench" / f"{plik}.jsonl").read_text().splitlines() if l.strip()]
        braki = 0
        for r in rows:
            sid = int(r["zrodlo"].rstrip("/").split("/")[-1])
            sedziowie, protokolanci = meta.get(sid, ([], []))
            braki += sid not in meta
            r["state"] = anonimizuj(r["state"], sedziowie, protokolanci)
        (OUT / f"{plik}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        print(f"{plik}: {len(rows)} orzeczeń, bez metadanych: {braki}")


if __name__ == "__main__":
    main()
