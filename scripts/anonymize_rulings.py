"""Replaces names of judges and court clerks in real jerzyk-bench rulings before publication.

  python -m scripts.anonymize_rulings     # → wydanie/anonimizacja/{sad_real_test,sad_real_fragmenty_test,sad_real_dev}.jsonl

SAOS anonymises the parties, but publishes the court panel. At the project author's request we replace:
- judges (SAOS metadata `judges`) → [SĘDZIA], clerks (`courtReporters`) → [PROTOKOLANT],
  also in the form „R. Troll” and by surname alone,
- as a precaution, first and last name after the words „Sędzia/SSR/SSO/SSA/Ławnik/Protokolant/Prokurator/referendarz”,
- a first name from a list of common first names (also inflected: „Urszuli”, „Zdzisława”) followed by a surname.
The metadata comes from the local SAOS dump (data/prawo/saos-od-*, see scripts/fetch_legal_sources.py).
Leaks the rules miss, found by reading every real document, are fixed by hand in MANUAL_FIXES; these are also
applied to the already anonymised notices (adm_real_test.jsonl).
"""
import argparse
import glob
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "wydanie" / "anonimizacja"
FILES = ["sad_real_test", "sad_real_fragmenty_test", "sad_real_dev"]
NOTICES = "adm_real_test"
# found by two independent read-throughs of all 296 real documents (2026-10-19); names of authors of cited legal
# commentaries are published literature and stay
MANUAL_FIXES = {
    "sad_real-000": [(" (Szok)", "")],                                     # former surname of a participant
    "sad_real-006": [("Sławomir [SĘDZIA]", "[SĘDZIA]")],                   # judge's first name in the signature
    "sad_real-027": [("ProtokolantBarbara [OSOBA]", "Protokolant [PROTOKOLANT]")],
    "sad_real_dev-001": [("EDUM/25/039230337", "[DANE]")],                 # ZUS decision number of the insured
    "sad_real_dev-027": [("[PROTOKOLANT] Fabiszewska", "[PROTOKOLANT]")],
    "sad_real_dev-047": [("Amina A. A.", "A. A.")],                        # first name of a plaintiff
    "sad_real_dev-073": [("Daniny N. U. (2)", "N. U. (2)")],               # first name of a participant
    "sad_real_dev-080": [("[SĘDZIA] Rizler", "[OSOBA]")],                  # court bailiff
    "adm_real-048": [("41 373 13 48", "[DANE]")],                          # direct line of the official who drafted it
    "adm_real-049": [("41 373 13 48", "[DANE]")],
    "adm_real-051": [("41 373 13 48", "[DANE]")],
}
CAP_WORD = r"(?!Protokolant|Przewodnicz|Sędzi|Ławni|Prokurator)[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+"
ROLE = re.compile(rf"((?:[Ss]ędzi(?:a|owie|ego|emu|ą|ów|ami)?|SSR|SSO|SSA|SR|SO|SA|[Łł]awni(?:k|cy)|[Pp]rotokolant(?:ka)?|[Pp]rokurator|"
                  rf"[Rr]eferendarz(?:\s+sądowy)?|[Ss]ekretarz\s+sądowy|[Aa]systent\s+sędziego|[Aa]sesor\s+sądowy|stażysta)"
                  rf"[\s:–\-.,()a-ząćęłńóśźżA-Z]{{0,40}}?)"
                  rf"\b({CAP_WORD}(?:\s*-\s*{CAP_WORD}|\s+{CAP_WORD}){{0,2}})\b(?!\.)")
# Last net: full "First Last" from common first names (SAOS pages already have initials) — in the panel [SĘDZIA], elsewhere [OSOBA].
FIRST_NAMES = ("Anna Maria Katarzyna Małgorzata Agnieszka Barbara Ewa Krystyna Elżbieta Magdalena Joanna Aleksandra Monika Beata "
               "Dorota Renata Iwona Jolanta Marta Justyna Urszula Karolina Dominika Agata Izabela Grażyna Halina Sylwia Edyta "
               "Paulina Ilona Teresa Danuta Bożena Alicja Natalia Kinga Emilia Lidia Wioletta Marzena Ewelina Zofia Hanna "
               "Piotr Krzysztof Andrzej Tomasz Paweł Jan Michał Marcin Marek Grzegorz Józef Łukasz Adam Zbigniew Jerzy Tadeusz "
               "Mariusz Dariusz Rafał Mirosław Wojciech Robert Jacek Janusz Maciej Sławomir Jarosław Kamil Wiesław Roman Damian "
               "Przemysław Stanisław Artur Bartosz Sebastian Mateusz Daniel Arkadiusz Ryszard Waldemar Leszek Bogdan Henryk "
               "Kazimierz Zdzisław Edward Witold Ireneusz Cezary Radosław Szymon Jakub Konrad Filip Dawid Norbert").split()


def inflections(name):
    """First name in the dependent cases (genitive, dative, accusative, instrumental, locative) — an approximation."""
    if name.endswith("ia"):          # Maria → Marii, Marię, Marią
        return {name, name[:-1] + "i", name[:-1] + "ę", name[:-1] + "ą"}
    if name.endswith(("la", "ja")):  # Urszula → Urszuli, Urszulę; Kinga ↓
        return {name, name[:-1] + "i", name[:-1] + "ę", name[:-1] + "ą"}
    if name.endswith("a"):           # Anna → Anny, Annie, Annę; Kinga → Kingi
        stem = name[:-1]
        return {name, stem + "y", stem + "i", stem + "ie", stem + "ę", stem + "ą"}
    if name.endswith("ek"):          # Marek → Marka, Markowi
        stem = name[:-2] + "k"
        return {name, stem + "a", stem + "owi", stem + "iem", stem + "u"}
    return {name, name + "a", name + "owi", name + "em", name + "ie", name + "u"}  # Zdzisław → Zdzisława


ALL_FIRST_NAMES = sorted({form for first in FIRST_NAMES for form in inflections(first)}, key=len, reverse=True)
FULL_NAME = re.compile(rf"\b(?:{'|'.join(ALL_FIRST_NAMES)})\s+{CAP_WORD}(?:\s*-\s*{CAP_WORD})?\b")
# First name left before a placeholder or before "..." (truncated text) in the court panel.
REST = re.compile(rf"\b{CAP_WORD}\s+(\[(?:SĘDZIA|PROTOKOLANT|OSOBA)\])")


def replace_names(text, people, placeholder):
    for person in sorted(people, key=len, reverse=True):
        parts = person.split()
        if len(parts) < 2:
            continue
        first, surname = parts[0], parts[-1]
        pattern = r"\s*-\s*".join(re.escape(x) for x in person.replace(" - ", "-").split("-"))
        text = re.sub(rf"\b{pattern}\b", placeholder, text)
        text = re.sub(rf"\b{re.escape(first)}\b(?=\s*(?:\.\.\.|\[|$))", placeholder, text)
        text = re.sub(rf"\b{re.escape(first[0])}\.\s*{re.escape(surname)}\b", placeholder, text)
        for part in re.split(r"[\s\-–]+", person):  # each part of a compound surname, also inflected
            if len(part) > 3:
                text = re.sub(rf"\b{re.escape(part)}\w{{0,3}}\b", placeholder, text)
        text = re.sub(rf"({re.escape(placeholder)})(?:\s*[–\-]\s*{re.escape(placeholder)})+", r"\1", text)
    return text


def anonymize(text, judges=(), clerks=()):
    """Text of a ruling without the names of the panel, prosecutors and clerks."""
    t = replace_names(text, judges, "[SĘDZIA]")
    t = replace_names(t, clerks, "[PROTOKOLANT]")
    t = ROLE.sub(lambda m: m.group(1) + ("[OSOBA]" if not m.group(2).startswith("[") else m.group(2)), t)
    t = REST.sub(r"\1", t)
    t = re.sub(rf"(\[(?:SĘDZIA|OSOBA|PROTOKOLANT)\])\s*[–\-]\s*{CAP_WORD}", r"\1", t)  # „[OSOBA] – Kuchta”
    t = re.sub(rf"(\[(?:SĘDZIA|OSOBA)\])\s+{CAP_WORD}\s+{CAP_WORD}\b(?!\s+(?:Sąd|Wydział))", r"\1 [SĘDZIA]", t)  # next panel member
    return FULL_NAME.sub("[SĘDZIA]", t[:1200]) + FULL_NAME.sub("[OSOBA]", t[1200:])


def apply_manual_fixes(row):
    """A copy of the row with the hand-made fixes for its document applied."""
    state = row["state"]
    for old, new in MANUAL_FIXES.get(row["id"], ()):
        state = state.replace(old, new)
    return {**row, "state": state}


def write_rows(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    meta = {}
    for f in glob.glob(str(ROOT / "data/prawo/saos-od-*/*.jsonl.gz")):
        for line in gzip.open(f, "rt", encoding="utf-8"):
            j = json.loads(line)
            meta[j["id"]] = ([x["name"] for x in j.get("judges", [])], j.get("courtReporters", []))
    OUT.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        rows, missing = [], 0
        for r in read_rows(ROOT / "data/bench" / f"{name}.jsonl"):
            sid = int(r["source"].rstrip("/").split("/")[-1])
            judges, clerks = meta.get(sid, ([], []))
            missing += sid not in meta
            rows.append(apply_manual_fixes({**r, "state": anonymize(r["state"], judges, clerks)}))
        write_rows(OUT / f"{name}.jsonl", rows)
        print(f"{name}: {len(rows)} rulings, without metadata: {missing}")
    notices = OUT / f"{NOTICES}.jsonl"
    write_rows(notices, [apply_manual_fixes(r) for r in read_rows(notices)])
    print(f"{NOTICES}: manual fixes applied")


if __name__ == "__main__":
    main()
