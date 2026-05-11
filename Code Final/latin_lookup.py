"""
Latin words database fallback.

Loads a CSV of Latin word forms once at import time and exposes a lookup
helper used when the morphological analyser's confidence is below threshold.
The same form can appear in multiple rows, so lookups return all possible
values for the requested feature.
"""

import csv
import unicodedata
from collections import defaultdict
from pathlib import Path


# Map intent label -> CSV column name
INTENT_TO_CSV_COLUMN = {
    "part_of_speech": "part_of_speech",
    "person":         "person",
    "mood":           "mood",
    "tense":          "tense",
    "voice":          "voice",
    "number":         "number",
    "case":           "case",
    "gender":         "gender",
    "aspect":         "aspect",
    "conjugation":    "conjugation",
    "declension":     "declension",
}


# map CSV codes to readable names
CSV_FEATURE_MAPPINGS = {
    "part_of_speech": {
        "ADJ": "adjective", "V": "verb", "N": "noun", "PROPN": "proper noun",
        "V.PTCP": "participle", "V+V.PTCP": "participle",
        "V.MSDR": "gerund", "V+V.MSDR": "gerund",
    },
    "gender": {
        "MASC": "masculine", "FEM": "feminine", "NEUT": "neuter",
        "MASC+FEM": "masculine or feminine", "MASC+NEUT": "masculine or neuter",
        "FEM+NEUT": "feminine or neuter", "MASC+FEM+NEUT": "masculine, feminine, or neuter",
    },
    "case": {
        "NOM": "nominative", "ACC": "accusative", "GEN": "genitive",
        "DAT": "dative", "ABL": "ablative", "VOC": "vocative", "LOC": "locative",
        "GEN+DAT": "genitive or dative",
    },
    "number": {"SG": "singular", "PL": "plural"},
    "tense":  {"PRS": "present", "PST": "past", "FUT": "future"},
    "aspect": {"IPFV": "imperfective", "PRF": "perfect", "PFV": "perfective"},
    "voice":  {"ACT": "active", "PASS": "passive"},
    "mood":   {"IND": "indicative", "SBJV": "subjunctive", "IMP": "imperative"},
    "person": {"1": "1st person", "2": "2nd person", "3": "3rd person"},
    "conjugation": {
        "1": "1st conjugation", "2": "2nd conjugation",
        "3": "3rd conjugation", "4": "4th conjugation",
    },
    "declension": {
        "1": "1st declension", "2": "2nd declension", "3": "3rd declension",
        "4": "4th declension", "5": "5th declension",
    },
    "degree": {"POS": "positive", "COMP": "comparative", "SUPER": "superlative"},
    "finiteness":      {"NFIN": "nonfinite"},
    "lang_specific":   {"LGSPEC1": "supine"},
    "participle_type": {"PPL": "participle"},
}


def _normalise(s: str) -> str:
    """
    Lowercase and strip combining marks (so 'veredarius' matches 'verēdārius').
    """
    decomposed = unicodedata.normalize("NFD", s)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.strip().lower()


class LatinWordsDB:
    """Form-keyed lookup over the Latin words CSV."""

    def __init__(self, csv_path: str | Path):
        self.csv_path = Path(csv_path)
        self._index: dict[str, list[dict]] = defaultdict(list)
        self._load()

    def _load(self):
        with open(self.csv_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                form_key = _normalise(row.get("form", ""))
                if form_key:
                    self._index[form_key].append(row)
        
        total = sum(len(v) for v in self._index.values())
        print(f"Loaded {total} entries covering {len(self._index)} unique forms from {self.csv_path}.")

    def lookup_feature(self, form: str, intent: str) -> list[str] | None:
        """
        Return all possible values for `intent` of the Latin `form`.

        Returns a sorted list of unique non-empty raw CSV values, or None if
        the word isn't in the DB or the feature is empty across all its rows.
        """
        column = INTENT_TO_CSV_COLUMN.get(intent)
        if not column:
            return None

        entries = self._index.get(_normalise(form))
        if not entries:
            return None

        values = {
            row[column].strip()
            for row in entries
            if row.get(column, "").strip()
        }
        return sorted(values) if values else None
    
    def supports_intent(self, intent: str) -> bool:
        """True if this intent maps to a column in the CSV."""
        return intent in INTENT_TO_CSV_COLUMN
    
    def feature_applies(self, form: str, intent: str) -> bool:
        """
        Whether `intent`'s feature applies to `form` in the DB.
        True if at least one row has a non-empty value for the column,
        False if every row's column is empty,
        True if the form isn't in the DB at all.
        """
        column = INTENT_TO_CSV_COLUMN.get(intent)
        if not column:
            return True
        entries = self._index.get(_normalise(form))
        if not entries:
            return True
        return any(row.get(column, "").strip() for row in entries)



def format_csv_values(values: list[str], column: str) -> str:
    """
    Turn ['GEN', 'NOM'] into 'genitive or nominative' for the given column.
    """
    mapping = CSV_FEATURE_MAPPINGS.get(column, {})
    pretty = [mapping.get(v, v.lower()) for v in values]
    if len(pretty) == 1:
        return pretty[0]
    if len(pretty) == 2:
        return f"{pretty[0]} or {pretty[1]}"
    return ", ".join(pretty[:-1]) + f", or {pretty[-1]}"


def build_fallback_response(db: LatinWordsDB, latin_word: str, intent: str, model_label: str | None = None) -> str:
    """
    Build a user-facing fallback message for a low-confidence prediction.

    Looks the word up in the DB and returns either the DB-grounded answer
    (single value or "ambiguous, could be A or B") or, if the word isn't
    in the DB, a response based on the model's best guess.
    """
    pretty_intent = intent.replace("_", " ")
    db_values = db.lookup_feature(latin_word, intent)

    print(f"[LOG] DB fallback for '{latin_word}' - {intent}: {db_values}")

    if db_values:
        formatted = format_csv_values(db_values, intent)

        if len(db_values) == 1:
            return f"The {pretty_intent} of '{latin_word}' is {formatted}."
        
        return (f"'{latin_word}' is ambiguous. Depending on context, "
                f"its {pretty_intent} could be {formatted}.")

    # Word not in DB; use the model's guess but acknowledge uncertainty.
    if model_label:
        return (f"I'm not confident about the {pretty_intent} of '{latin_word}'. "
                f"It might be {model_label}, but I'm not sure.")
    
    return (f"I'm not confident about the {pretty_intent} of '{latin_word}', "
            f"and I couldn't find it in my dictionary.")

