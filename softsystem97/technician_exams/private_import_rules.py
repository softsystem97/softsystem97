"""Parser for confidential N4 import: no Frappe, network, or secret output."""
import csv
import hashlib
import io
from .rules import validate_question

COLUMNS = ("track", "category", "prompt", "options_json", "correct_option",
           "critical", "is_active")

def check_n4_csv(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 200000:
        raise ValueError("CSV N4 absent ou trop volumineux.")
    try:
        stream = io.StringIO(raw.decode("utf-8-sig"), newline="")
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError("Modèle CSV non conforme.")
        questions, seen = [], set()
        for number, row in enumerate(reader, 1):
            if (number > 40 or None in row or row.get("track") != "CYBER"
                    or row.get("critical") not in ("0", "1")
                    or row.get("is_active") != "0"):
                raise ValueError(f"Ligne {number} non conforme ou active.")
            try:
                validate_question(row["prompt"], row["options_json"],
                                  row["correct_option"], row["category"])
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(f"Ligne {number} : question invalide.") from exc
            normalized = " ".join(row["prompt"].casefold().split())
            if normalized in seen:
                raise ValueError(f"Ligne {number} : énoncé déjà présent.")
            seen.add(normalized)
            questions.append({
                "track": "CYBER", "category": row["category"].strip(),
                "prompt": row["prompt"].strip(), "options_json": row["options_json"],
                "correct_option": row["correct_option"],
                "critical": int(row["critical"]), "is_active": 0,
            })
        if len(questions) != 40:
            raise ValueError("40 questions N4 exactement sont nécessaires.")
    except UnicodeError as exc:
        raise ValueError("Encodage UTF-8 requis.") from exc
    return {"questions": questions, "sha256": hashlib.sha256(raw).hexdigest()}
