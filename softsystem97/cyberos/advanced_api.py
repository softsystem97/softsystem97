"""CyberOS v2: safe inventory links, continuity registers and tabletop exercises."""
from uuid import uuid4

import frappe
from .api import _company, _manager, _owned, _rows, ASSET, ACTION, INCIDENT
from .logic import choice, identifier, text
from .advanced_logic import dependency_data, continuity_data, drill_data, executive_summary

DEPENDENCY = "SS97 Cyber Dependency"
CONTINUITY = "SS97 Cyber Continuity"
DRILL = "SS97 Cyber Drill"


def _available():
    # The original _company() checks both feature flags, Customer isolation and migration.
    user, customer = _company()
    if not all(frappe.db.exists("DocType", x) for x in (DEPENDENCY, CONTINUITY, DRILL)):
        frappe.throw("Migration CyberOS v2 requise.", frappe.PermissionError)
    return user, customer


def _add(doctype, data, user, customer, id_field):
    doc = frappe.get_doc({"doctype": doctype, id_field: str(uuid4()),
                          "customer": customer, "created_by_user": user, **data})
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "state": doc.get("state")}


@frappe.whitelist(methods=["POST"])
def map_dependency(source_asset, target_asset, description):
    user, customer = _available()
    try:
        data = dependency_data(source_asset, target_asset, description)
    except ValueError as exc:
        frappe.throw(str(exc), frappe.ValidationError)
    # Both endpoints must be in the SAME Customer; no cross-tenant graph.
    _owned(ASSET, data["source_asset"], customer)
    _owned(ASSET, data["target_asset"], customer)
    return _add(DEPENDENCY, {**data, "state": "DECLARED"}, user, customer, "dependency_id")


@frappe.whitelist(methods=["POST"])
def create_continuity_plan(service, scenario, impact, fallback_steps, owner_role):
    user, customer = _available()
    try:
        data = continuity_data(service, scenario, impact, fallback_steps, owner_role)
    except ValueError as exc:
        frappe.throw(str(exc), frappe.ValidationError)
    return _add(CONTINUITY, {**data, "state": "DRAFT"}, user, customer, "plan_id")


@frappe.whitelist(methods=["POST"])
def prepare_drill(scenario, objectives):
    user, customer = _available()
    try:
        data = drill_data(scenario, objectives)
    except ValueError as exc:
        frappe.throw(str(exc), frappe.ValidationError)
    return _add(DRILL, {**data, "state": "PLANNED"}, user, customer, "drill_id")


@frappe.whitelist(methods=["POST"])
def record_drill_result(drill_id, lessons):
    _, customer = _available()
    try:
        lessons = text(lessons, 1600, "Enseignements")
    except ValueError as exc:
        frappe.throw(str(exc), frappe.ValidationError)
    doc = _owned(DRILL, drill_id, customer, lock=True)
    if doc.state != "PLANNED":
        frappe.throw("Exercice déjà déclaré ou revu.", frappe.PermissionError)
    doc.lessons = lessons
    doc.state = "COMPLETED_DECLARED"
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "state": doc.state}


@frappe.whitelist(methods=["POST"])
def manager_review_plan(plan_id):
    manager = _manager()
    try:
        plan_id = identifier(plan_id)
    except ValueError as exc:
        frappe.throw(str(exc), frappe.ValidationError)
    if not frappe.db.exists(CONTINUITY, plan_id):
        frappe.throw("Plan introuvable.", frappe.PermissionError)
    doc = frappe.get_doc(CONTINUITY, plan_id, for_update=True)
    if doc.state != "DRAFT":
        frappe.throw("Plan non éligible à la revue.", frappe.PermissionError)
    doc.state = "REVIEWED"
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "state": doc.state, "reviewed_by": manager}


@frappe.whitelist(methods=["GET"])
def get_my_cyberos_v2():
    _, customer = _available()
    assets = _rows(ASSET, customer, ["name", "label", "kind", "criticality"])
    actions = _rows(ACTION, customer, ["name", "summary", "priority", "state"])
    incidents = _rows(INCIDENT, customer, ["name", "summary", "severity", "state"])
    links = _rows(DEPENDENCY, customer, ["name", "source_asset", "target_asset", "description", "state"])
    plans = _rows(CONTINUITY, customer, ["name", "service", "scenario", "impact", "owner_role", "state"])
    drills = _rows(DRILL, customer, ["name", "scenario", "objectives", "state"])
    return {
        "assets": assets, "dependencies": links, "plans": plans, "drills": drills,
        "executive": executive_summary(assets, actions, incidents, links, plans, drills),
        "status": {
            "CyberTwin": "cartographie déclarative disponible",
            "CyberRecovery": "plans déclaratifs disponibles",
            "CyberLab": "exercices enregistrés, aucune simulation automatique",
            "CyberDirector": "indicateurs déclaratifs disponibles",
            "CyberAI": "non connecté", "CyberPulse": "non connecté",
            "CyberSentinel": "non connecté", "CyberSOS": "aucune astreinte garantie"
        },
    }
