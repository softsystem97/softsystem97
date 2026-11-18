"""Pure examination rules. No Frappe session, permissions or network side effects.

Question texts and answer keys must be maintained in a private Frappe DocType,
never embedded in public JavaScript or GitHub fixtures.
"""

import json
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ExamTrack:
    code: str
    label: str
    question_count: int
    minutes: int
    required_correct: int


TRACKS = {
    "L2": ExamTrack("L2", "Technicien informatique généraliste", 20, 20, 14),
    "BANK": ExamTrack("BANK", "Informatique bancaire", 30, 25, 24),
    "CYBER": ExamTrack("CYBER", "Expert cybersécurité — niveau 4", 40, 20, 34),
}
OPTION_IDS = ("A", "B", "C", "D")
MAX_ATTEMPTS = 2


def track_for(code):
    if not isinstance(code, str) or code not in TRACKS:
        raise ValueError("Filière d'examen inconnue.")
    return TRACKS[code]


def validate_question(prompt, options_json, correct_option, category=""):
    if not isinstance(prompt, str) or not 12 <= len(prompt.strip()) <= 1000:
        raise ValueError("Énoncé obligatoire (12 à 1000 caractères).")
    if not isinstance(options_json, str) or len(options_json) > 6000:
        raise ValueError("Options invalides.")
    try:
        options = json.loads(options_json)
    except (ValueError, TypeError) as exc:
        raise ValueError("Les options doivent être du JSON valide.") from exc
    if not isinstance(options, dict) or set(options) != set(OPTION_IDS):
        raise ValueError("Quatre options A, B, C et D sont obligatoires.")
    if any(not isinstance(value, str) or not 1 <= len(value.strip()) <= 500
           for value in options.values()):
        raise ValueError("Chaque réponse doit comporter 1 à 500 caractères.")
    if correct_option not in OPTION_IDS:
        raise ValueError("La bonne réponse doit être A, B, C ou D.")
    if not isinstance(category, str) or len(category) > 80:
        raise ValueError("Catégorie invalide.")
    return {key: options[key].strip() for key in OPTION_IDS}


def public_questions(snapshot):
    """Never disclose correct_option, critical or other private review fields."""
    return [{"id": q["id"], "prompt": q["prompt"],
             "category": q.get("category", ""),
             "options": q["options"]} for q in snapshot]


def grade(track, snapshot, answers):
    config = track_for(track)
    if len(snapshot) != config.question_count:
        raise ValueError("Examen incomplet : nombre de questions incorrect.")
    if not isinstance(answers, dict):
        raise ValueError("Réponses invalides.")
    ids = [q["id"] for q in snapshot]
    if len(set(ids)) != len(ids) or set(answers) - set(ids):
        raise ValueError("Questions ou réponses incohérentes.")
    if any(answer not in OPTION_IDS for answer in answers.values()):
        raise ValueError("Réponse inconnue.")
    correct = sum(answers.get(q["id"]) == q["correct_option"] for q in snapshot)
    critical_errors = sum(bool(q.get("critical")) and
                          answers.get(q["id"]) != q["correct_option"]
                          for q in snapshot)
    return {"correct": correct, "total": config.question_count,
            "required_correct": config.required_correct,
            "percentage": round(correct * 100 / config.question_count, 1),
            "critical_errors": critical_errors,
            "passed": correct >= config.required_correct and critical_errors == 0}


def seconds_remaining(deadline: datetime, current: datetime):
    """Server-side authority; browser countdown is only a display."""
    return max(0, int((deadline - current).total_seconds()))
