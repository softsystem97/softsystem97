"""Opt-in Frappe v16 examination service for *candidate* technicians.

Never assigns technician roles, provisions accounts, initiates MeshCentral,
charges Stripe, or shares answer keys. A separate human review is mandatory.
"""

import json
import secrets
from datetime import timedelta
from uuid import uuid4

import frappe
from frappe.utils import get_datetime, now_datetime

from .rules import (
    MAX_ATTEMPTS, TRACKS, grade, public_questions, seconds_remaining,
    track_for, validate_question,
)


QUESTION = "SS97 Technician Exam Question"
ATTEMPT = "SS97 Technician Exam Attempt"
ALLOWED_CANDIDATE_ROLES = frozenset({"Candidat SS97", "System Manager"})


def _candidate():
    user = frappe.session.user
    if not user or user == "Guest" or not (
        set(frappe.get_roles(user)) & ALLOWED_CANDIDATE_ROLES
    ):
        frappe.throw("Compte candidat autorisé requis.", frappe.PermissionError)
    if not frappe.db.get_value("User", user, "enabled"):
        frappe.throw("Compte désactivé.", frappe.PermissionError)
    return user


def _enabled():
    config = frappe.conf.get("ss97_technician_exams") or {}
    if not isinstance(config, dict) or config.get("enabled") is not True:
        frappe.throw("Examens non activés sur ce site.", frappe.PermissionError)
    if not frappe.db.table_exists(QUESTION) or not frappe.db.table_exists(ATTEMPT):
        frappe.throw("Migration des examens SS97 manquante.", frappe.PermissionError)


def _lock_user(user):
    # Serializes concurrent starts for a given candidate, not the entire bank.
    if not frappe.db.sql("SELECT name FROM `tabUser` WHERE name=%s FOR UPDATE", (user,)):
        frappe.throw("Compte candidat introuvable.", frappe.PermissionError)


def _require_selected_track(user, track):
    """When TECH OS is on, an exam may only target the applicant's own track."""
    config = frappe.conf.get("ss97_tech_os") or {}
    if not isinstance(config, dict) or config.get("enabled") is not True:
        return  # Existing examination-only pilot remains independent.
    profile_type = "SS97 Technician Profile"
    if not frappe.db.table_exists(profile_type):
        frappe.throw("Profil technicien non migré.", frappe.PermissionError)
    profile = frappe.db.get_value(
        profile_type, {"candidate_user": user}, ["track", "state"], as_dict=True,
    )
    if (not profile or profile.track != track or profile.state != "IN_REVIEW"):
        frappe.throw("Examen réservé à la filière de votre candidature.", frappe.PermissionError)


def _attempt(attempt_id, user, lock=False):
    if not isinstance(attempt_id, str) or len(attempt_id) != 36:
        frappe.throw("Session d'examen invalide.", frappe.PermissionError)
    if lock and not frappe.db.sql(
        f"SELECT name FROM `tab{ATTEMPT}` WHERE name=%s FOR UPDATE", (attempt_id,)
    ):
        frappe.throw("Session d'examen introuvable.", frappe.PermissionError)
    if not frappe.db.exists(ATTEMPT, attempt_id):
        frappe.throw("Session d'examen introuvable.", frappe.PermissionError)
    doc = frappe.get_doc(ATTEMPT, attempt_id)
    if doc.candidate_user != user:
        frappe.throw("Examen inaccessible.", frappe.PermissionError)
    return doc


def _snapshot(doc):
    return json.loads(doc.snapshot_json)


def _answers(doc):
    return json.loads(doc.answers_json or "{}")


def _seconds(doc):
    return seconds_remaining(get_datetime(doc.deadline_at), now_datetime())


def _result(doc):
    return {
        "attempt_id": doc.name, "track": doc.track, "state": doc.state,
        "correct": int(doc.correct_count or 0),
        "total": track_for(doc.track).question_count,
        "required_correct": track_for(doc.track).required_correct,
        "percentage": float(doc.score_percentage or 0),
        "note": "Résultat technique provisoire. Aucune habilitation automatique.",
    }


def _public_attempt(doc):
    remaining = _seconds(doc) if doc.state == "IN_PROGRESS" else 0
    if doc.state != "IN_PROGRESS":
        return _result(doc)
    if remaining == 0:
        # GET never mutates records. Client must POST submit_exam to finalize.
        return {"attempt_id": doc.name, "track": doc.track, "state": "TIME_UP",
                "seconds_remaining": 0, "questions": [], "answers": {}}
    return {"attempt_id": doc.name, "track": doc.track,
            "state": "IN_PROGRESS", "seconds_remaining": remaining,
            "questions": public_questions(_snapshot(doc)), "answers": _answers(doc)}


def _finish(doc, timed_out=False):
    if doc.state != "IN_PROGRESS":
        return _result(doc)
    summary = grade(doc.track, _snapshot(doc), _answers(doc))
    doc.correct_count = summary["correct"]
    doc.score_percentage = summary["percentage"]
    doc.state = ("EXPIRED" if timed_out else
                 "PASSED" if summary["passed"] else "FAILED")
    doc.submitted_at = now_datetime()
    doc.save(ignore_permissions=True)
    return _result(doc)


@frappe.whitelist(methods=["GET"])
def get_catalog():
    _enabled()
    user = _candidate()
    codes = tuple(TRACKS)
    config = frappe.conf.get("ss97_tech_os") or {}
    if isinstance(config, dict) and config.get("enabled") is True:
        profile_type = "SS97 Technician Profile"
        if not frappe.db.table_exists(profile_type):
            frappe.throw("Profils techniciens non migrés.", frappe.PermissionError)
        profile = frappe.db.get_value(profile_type, {"candidate_user": user},
                                      ["track", "state"], as_dict=True)
        codes = (profile.track,) if profile and profile.state == "IN_REVIEW" else ()
    return {"tracks": [
        {"code": cfg.code, "label": cfg.label,
         "question_count": cfg.question_count, "minutes": cfg.minutes,
         "required_correct": cfg.required_correct}
        for code, cfg in TRACKS.items() if code in codes],
        "notice": "Examen professionnel de présélection : validation humaine obligatoire."}


@frappe.whitelist(methods=["POST"])
def start_exam(track):
    _enabled()
    user = _candidate()
    settings = track_for(track)
    _require_selected_track(user, track)
    _lock_user(user)
    open_rows = frappe.get_all(
        ATTEMPT, filters={"candidate_user": user, "track": track,
                          "state": "IN_PROGRESS"},
        fields=["name"], order_by="creation desc", limit_page_length=2,
    )
    for row in open_rows:
        current = _attempt(row.name, user, lock=True)
        if _seconds(current) > 0:
            return _public_attempt(current)
        _finish(current, timed_out=True)

    if frappe.db.count(ATTEMPT, {"candidate_user": user, "track": track}) >= MAX_ATTEMPTS:
        frappe.throw("Nombre maximum de tentatives atteint. Contactez SS97.", frappe.PermissionError)

    rows = frappe.get_all(
        QUESTION, filters={"track": track, "is_active": 1},
        fields=["name", "prompt", "options_json", "correct_option", "critical", "category"],
        limit_page_length=501,
    )
    if len(rows) > 500:
        frappe.throw("Banque de questions à vérifier par l'administrateur.", frappe.PermissionError)
    if len(rows) < settings.question_count:
        frappe.throw("Examen indisponible : banque de questions insuffisante.", frappe.PermissionError)

    chosen = secrets.SystemRandom().sample(rows, settings.question_count)
    snapshot = []
    for item in chosen:
        try:
            options = validate_question(item.prompt, item.options_json,
                                        item.correct_option, item.category or "")
        except ValueError:
            frappe.throw("Banque de questions invalide : contactez SS97.", frappe.PermissionError)
        snapshot.append({"id": item.name, "prompt": item.prompt.strip(),
                         "options": options, "correct_option": item.correct_option,
                         "category": item.category or "", "critical": bool(item.critical)})

    now = now_datetime()
    doc = frappe.get_doc({
        "doctype": ATTEMPT, "attempt_id": str(uuid4()), "candidate_user": user,
        "track": track, "state": "IN_PROGRESS", "started_at": now,
        "deadline_at": now + timedelta(minutes=settings.minutes),
        "snapshot_json": json.dumps(snapshot, ensure_ascii=False),
        "answers_json": "{}",
    }).insert(ignore_permissions=True)
    return _public_attempt(doc)


@frappe.whitelist(methods=["GET"])
def get_exam(attempt_id):
    _enabled()
    return _public_attempt(_attempt(attempt_id, _candidate()))


@frappe.whitelist(methods=["POST"])
def save_answer(attempt_id, question_id, selected_option):
    _enabled()
    doc = _attempt(attempt_id, _candidate(), lock=True)
    if doc.state != "IN_PROGRESS":
        return _result(doc)
    if _seconds(doc) == 0:
        return _finish(doc, timed_out=True)
    if not isinstance(question_id, str) or not isinstance(selected_option, str):
        frappe.throw("Réponse invalide.", frappe.PermissionError)
    if selected_option not in ("A", "B", "C", "D"):
        frappe.throw("Option inconnue.", frappe.PermissionError)
    if question_id not in {item["id"] for item in _snapshot(doc)}:
        frappe.throw("Question étrangère à cet examen.", frappe.PermissionError)
    answers = _answers(doc)
    answers[question_id] = selected_option
    doc.answers_json = json.dumps(answers, sort_keys=True)
    doc.save(ignore_permissions=True)
    return {"saved": True, "seconds_remaining": _seconds(doc)}


@frappe.whitelist(methods=["POST"])
def submit_exam(attempt_id):
    _enabled()
    doc = _attempt(attempt_id, _candidate(), lock=True)
    return _finish(doc, timed_out=_seconds(doc) == 0)
