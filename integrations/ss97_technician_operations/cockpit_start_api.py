"""Recovered cockpit generator. No deployment, password or user mutation on import.

This API stays disabled pending reviewed business/notification adapters. Optional
WhatsApp code is not substituted or enabled when unavailable.
"""

API_SCRIPT_NAME = "SS97 Cockpit Intervention API"
API_METHOD = "ss97_cockpit_intervention"

SCRIPT_PREFIX = r"""
# SoftSystem97 — Cockpit Intervention API
# RestrictedPython — pas d'import
action = frappe.form_dict.get("action") or ""
issue_name = frappe.form_dict.get("issue") or frappe.form_dict.get("ticket") or ""
motif = frappe.form_dict.get("motif") or ""
user = frappe.session.user


# Bound native gate precedes optional notification code and Issue access.
frappe.call("softsystem97.integrations.historical_ticket_guard.require_cockpit_session",
    issue_name=issue_name, action=action)
"""

SCRIPT_BODY = r"""
def now_ts():
    return frappe.utils.now()

def paid_ok(doc):
    # The private server authorizer must establish payment or a real exemption.
    return bool(frappe.call("softsystem97.integrations.historical_ticket_guard.require_cockpit_session",
        issue_name=doc.name, action="start"))


def tech_label(email):
    try:
        fn = frappe.db.get_value("User", email, "full_name")
        if fn:
            return fn
    except Exception:
        pass
    return email or "Technicien"

def user_is_technician():
    return bool(frappe.get_all("Has Role", filters={"parent": user, "parenttype": "User",
        "role": "SS97 Technician"}, fields=["role"], limit_page_length=1))


def ensure_assignment(doc):
    if (doc.get("ss97_technician") or "") == user and user_is_technician():
        return {"ok": 1, "why": ""}
    return {"ok": 0, "why": "Affectation administrative et rôle technicien requis."}


def event_code(title, status):
    t = str(title or "").upper()
    s = str(status or "")
    if "CONNECT" in t:
        return "TECHNICIEN_CONNECTE"
    if s in ("Clôturé", "Ticket clôturé", "Fermé") or "FERM" in t:
        return "TICKET_FERME"
    if "TERMIN" in t or s == "Intervention terminée":
        return "TICKET_TERMINE"
    if "RAPPORT" in t or s == "Rapport soumis":
        return "RAPPORT_SOUMIS"
    if "CLÔTURE" in t or "CLOTURE" in t or s == "Validation administrateur en attente":
        return "CLOTURE_DEMANDEE"
    if "COMMENC" in t or s in ("Intervention en cours", "En cours"):
        return "INTERVENTION_COMMENCEE"
    if "ACCEPT" in t or s in ("Accepté par le technicien", "Accepté"):
        return "TICKET_ACCEPTE"
    return (t.replace(" ", "_"))[:80]

def action_human(code):
    labels = {
        "TECHNICIEN_CONNECTE": "Technicien connecté",
        "TICKET_ACCEPTE": "Ticket accepté",
        "INTERVENTION_COMMENCEE": "Intervention commencée",
        "RAPPORT_SOUMIS": "Rapport soumis",
        "CLOTURE_DEMANDEE": "Clôture demandée",
        "TICKET_TERMINE": "Ticket terminé",
        "TICKET_FERME": "Ticket fermé",
    }
    return labels.get(str(code or ""), str(code or "Activité technicien"))

def notify_gwen(event_title, ticket_name, status_label):
    try:
        if not frappe.db.exists("DocType", "SS97 Gwen Event"):
            return
        ts = now_ts()
        tn = str(ticket_name or "")
        code = event_code(event_title, status_label)
        human = action_human(code)
        tech_name = tech_label(user)
        client_name = ""
        is_test = 0
        iss = None
        try:
            iss = frappe.get_doc("Issue", tn)
            client_name = str(iss.get("ss97_client_name") or iss.get("customer") or "")
            subj = str(iss.get("subject") or "")
            pay = str(iss.get("ss97_payment_status") or "").strip().lower()
            if not status_label:
                status_label = str(iss.get("ss97_ticket_status") or "")
        except Exception:
            pass
        date_part = str(ts)[:10]
        time_part = str(ts)[11:19]
        title = "🔧 SOFT SYSTEM 97 — ACTIVITÉ TECHNICIEN"
        body = (
            "🔧 SOFT SYSTEM 97 — ACTIVITÉ TECHNICIEN\n"
            "Ticket : " + tn + "\n"
            "Technicien : " + str(tech_name) + "\n"
            "Action : " + human + "\n"
            "Client : " + str(client_name or "—") + "\n"
            "Date : " + date_part + "\n"
            "Heure : " + time_part + "\n"
            "Statut : " + str(status_label or "—")
        )
        if is_test:
            body = body + "\nMODE : TEST"
        payload_txt = (
            '{"ticket":"' + tn.replace('"', "") + '"'
            + ',"technician":"' + str(tech_name).replace('"', "") + '"'
            + ',"client":"' + str(client_name).replace('"', "") + '"'
            + ',"status":"' + str(status_label or "").replace('"', "") + '"'
            + ',"activity":"' + str(code).replace('"', "") + '"'
            + ',"action":"' + str(human).replace('"', "") + '"}'
        )
        idem = ("tech|" + tn + "|" + code)[:180]
        existing = frappe.get_all("SS97 Gwen Event", filters={"idempotency_key": idem}, fields=["name"], limit=1)
        if existing:
            return
        ev = frappe.get_doc({
            "doctype": "SS97 Gwen Event",
            "event_type": "technician_activity",
            "priority": "INFORMATION",
            "title": title[:180],
            "summary": ("Ticket " + tn + " — " + human)[:1000],
            "payload_json": payload_txt,
            "source_module": "espace_technicien",
            "reference_doctype": "Issue",
            "reference_name": tn[:140],
            "actor": user,
            "internal_link": "/espace-technicien/intervention?ticket=" + tn,
            "is_test": is_test,
            "idempotency_key": idem,
            "channel_internal": 1,
            "channel_email": 0,
            "channel_whatsapp": 0,
            "delivery_status": "Pending",
            "occurred_at": ts,
        })
        ev.insert(ignore_permissions=True)
        nl_ok = 0
        try:
            nl = frappe.get_doc({
                "doctype": "Notification Log",
                "subject": (title + " — " + human)[:140],
                "email_content": body.replace("\n", "<br>")[:2000],
                "for_user": user,
                "owner": user,
                "type": "Alert",
                "from_user": user,
                "document_type": "Issue",
                "document_name": tn,
            })
            nl.insert(ignore_permissions=True)
            nl_ok = 1
        except Exception:
            nl_ok = 0
        frappe.db.set_value("SS97 Gwen Event", ev.name, {
            "channel_internal": 1 if nl_ok else 0,
            "delivery_status": "Delivered" if nl_ok else "Partial",
            "delivery_detail": body[:2000],
        }, update_modified=False)
        wa_to = ""
        try:
            if frappe.db.exists("DocType", "SS97 Gwen Notif Settings"):
                s = frappe.get_single("SS97 Gwen Notif Settings")
                wa_to = str(s.admin_whatsapp or "")
        except Exception:
            pass
        duree = ""
        try:
            mins = iss.get("ss97_actual_duration_min") if iss else None
            if mins:
                duree = str(mins) + " min"
        except Exception:
            duree = ""
        if not wa_to:
            return  # No private hardcoded fallback recipient.
        wa_res = gwen_deliver_tech_wa(idem, tn, tech_name, client_name, code, time_part, date_part, str(status_label or ""), duree, "", "", wa_to, ev.name)
        if wa_res.get("ok"):
            frappe.db.set_value("SS97 Gwen Event", ev.name, {
                "channel_internal": 1 if nl_ok else 0,
                "channel_whatsapp": 1,
                "delivery_status": "Delivered",
            }, update_modified=False)
        else:
            frappe.db.set_value("SS97 Gwen Event", ev.name, {
                "channel_internal": 1 if nl_ok else 0,
                "channel_whatsapp": 0,
                "delivery_status": "Partial",
                "delivery_detail": ("WHATSAPP_FAILED " + str(wa_res.get("error") or ""))[:2000],
            }, update_modified=False)
    except Exception:
        pass

def missing_for_start(doc):
    miss = []
    if not user or user == "Guest":
        miss.append("Vous devez être connecté.")
        return miss
    assign_res = ensure_assignment(doc)
    if not assign_res.get("ok"):
        miss.append(assign_res.get("why") or "Affectation technicien impossible.")
    st = doc.get("ss97_ticket_status") or ""
    closed = ["Clôturé", "Ticket clôturé", "Annulé", "Archivé", "Fermé"]
    if st in closed:
        miss.append("Le ticket est clôturé ou annulé.")
    accepted_states = ["Accepté par le technicien", "Accepté", "Prêt à commencer", "Technicien affecté", "Affecté au technicien", "Intervention en pause", "En pause"]
    accepted = bool(doc.get("ss97_accepted_on")) or (st in accepted_states)
    if not accepted:
        miss.append("Le ticket doit être accepté.")
    if not paid_ok(doc):
        miss.append("PAIEMENT EN ATTENTE — confirmez le paiement avant de démarrer (statut: " + str(doc.get("ss97_payment_status") or "non payé") + ").")
    try:
        if doc.meta.has_field("ss97_checklist_pre_done") and not doc.get("ss97_checklist_pre_done"):
            miss.append("La checklist avant intervention doit être terminée.")
    except Exception:
        pass
    if doc.get("ss97_security_suspend"):
        miss.append("Suspension sécurité active — validation administrateur requise.")
    if st == "Suspendu — risque sécurité":
        miss.append("Suspension sécurité active — validation administrateur requise.")
    active_states = ["Intervention en cours", "En cours", "Diagnostic en cours", "Session distante active"]
    if doc.get("ss97_intervention_started_on") and st in active_states:
        miss.append("Une intervention est déjà active sur ce ticket.")
    try:
        others = frappe.get_all(
            "Issue",
            filters={
                "ss97_technician": user,
                "ss97_ticket_status": ["in", ["Intervention en cours", "Session distante active"]],
                "name": ["!=", doc.name],
            },
            fields=["name"],
            limit=1,
        )
        if others:
            miss.append("Une session incompatible est en cours sur un autre ticket.")
    except Exception:
        pass
    return miss

def append_human(doc, line):
    prev = (doc.get("ss97_action_log") or "").strip()
    doc.ss97_action_log = (prev + "\n" + line).strip() if prev else line

def append_transition(doc, old, new, comment):
    prev = (doc.get("ss97_status_transition_log") or "").strip()
    line = "[" + str(now_ts()) + "] TRANSITION | " + old + " → " + new + " | technicien=" + tech_label(user) + " | " + comment
    doc.ss97_status_transition_log = (prev + "\n" + line).strip() if prev else line

if not issue_name:
    frappe.response["message"] = {"ok": 0, "error": "Ticket manquant", "missing": ["Ticket manquant"]}
elif action == "start":
    doc = frappe.get_doc("Issue", issue_name)
    # Affectation préalable (si autorisée) avant contrôles
    ensure_assignment(doc)
    miss = missing_for_start(doc)
    if miss:
        frappe.response["message"] = {
            "ok": 0,
            "error": "Impossible de démarrer l'intervention",
            "title": "IMPOSSIBLE DE DÉMARRER L'INTERVENTION",
            "missing": miss,
            "payment_status": doc.get("ss97_payment_status") or "",
            "technician": doc.get("ss97_technician") or "",
            "ticket_status": doc.get("ss97_ticket_status") or "",
        }
    else:
        old = doc.get("ss97_ticket_status") or ""
        ts = now_ts()
        doc.ss97_ticket_status = "Intervention en cours"
        doc.status = 'Open'
        doc.ss97_intervention_started_on = ts
        doc.ss97_timer_resumed_on = ts
        doc.ss97_pause_started_on = None
        doc.ss97_work_seconds = 0
        doc.ss97_pause_seconds = 0
        try:
            doc.ss97_timer_status = "running"
        except Exception:
            pass
        try:
            doc.ss97_next_action = "Réaliser le diagnostic initial"
        except Exception:
            pass
        doc.ss97_client_message = "Votre technicien a commencé l'intervention. Statut : Intervention en cours."
        append_human(doc, "[" + str(ts) + "] — Intervention commencée par " + tech_label(user) + ".")
        append_transition(doc, old, "Intervention en cours", "début=" + str(ts) + " | suite=diagnostic initial")
        doc.save(ignore_permissions=True)
        notify_gwen("INTERVENTION COMMENCÉE", doc.name, "Intervention en cours")
        frappe.response["message"] = {
            "ok": 1,
            "title": "INTERVENTION DÉMARRÉE",
            "ticket": doc.name,
            "technician": tech_label(user),
            "status": "Intervention en cours",
            "started_at": str(ts),
            "timer_status": "running",
            "next_action": "Réaliser le diagnostic initial",
            "chrono": "Actif",
        }
elif action == "pause":
    doc = frappe.get_doc("Issue", issue_name)
    if (doc.get("ss97_technician") or "") != user:
        frappe.response["message"] = {"ok": 0, "error": "Accès refusé", "missing": ["Technicien non autorisé"]}
    else:
        st = doc.get("ss97_ticket_status") or ""
        if st in ("Intervention en pause", "En pause"):
            frappe.response["message"] = {"ok": 0, "error": "Déjà en pause", "missing": ["Intervention déjà en pause"]}
        else:
            old = st
            ts = now_ts()
            # figer le temps côté serveur si possible
            accum = int(doc.get("ss97_work_seconds") or 0)
            base = doc.get("ss97_timer_resumed_on") or doc.get("ss97_intervention_started_on")
            if base and not doc.get("ss97_pause_started_on"):
                try:
                    delta = frappe.utils.time_diff_in_seconds(ts, base)
                    if delta and delta > 0:
                        accum = accum + int(delta)
                except Exception:
                    pass
            doc.ss97_work_seconds = accum
            doc.ss97_pause_started_on = ts
            doc.ss97_ticket_status = "Intervention en pause"
            doc.status = 'On Hold'
            try:
                doc.ss97_timer_status = "paused"
            except Exception:
                pass
            append_human(doc, "[" + str(ts) + "] — Intervention mise en pause" + ((" — " + motif) if motif else "") + ".")
            append_transition(doc, old, "Intervention en pause", "motif=" + (motif or "—"))
            doc.save(ignore_permissions=True)
            frappe.response["message"] = {"ok": 1, "title": "INTERVENTION EN PAUSE", "work_seconds": accum, "status": "Intervention en pause"}
elif action == "resume":
    doc = frappe.get_doc("Issue", issue_name)
    if (doc.get("ss97_technician") or "") != user:
        frappe.response["message"] = {"ok": 0, "error": "Accès refusé", "missing": ["Technicien non autorisé"]}
    elif doc.get("ss97_security_suspend") or (doc.get("ss97_ticket_status") or "") == "Suspendu — risque sécurité":
        frappe.response["message"] = {
            "ok": 0,
            "error": "Suspension sécurité active — validation administrateur requise",
            "missing": ["Suspension sécurité active — validation administrateur requise"],
            "title": "REPRISE BLOQUÉE",
        }
    else:
        st = doc.get("ss97_ticket_status") or ""
        if st not in ("Intervention en pause", "En pause"):
            frappe.response["message"] = {"ok": 0, "error": "Le ticket n'est pas en pause", "missing": ["Intervention non en pause"]}
        else:
            old = st
            ts = now_ts()
            if doc.get("ss97_pause_started_on"):
                try:
                    psec = int(doc.get("ss97_pause_seconds") or 0)
                    psec = psec + int(frappe.utils.time_diff_in_seconds(ts, doc.ss97_pause_started_on) or 0)
                    doc.ss97_pause_seconds = max(0, psec)
                except Exception:
                    pass
            doc.ss97_pause_started_on = None
            doc.ss97_timer_resumed_on = ts
            doc.ss97_ticket_status = "Intervention en cours"
            doc.status = 'Open'
            try:
                doc.ss97_timer_status = "running"
            except Exception:
                pass
            append_human(doc, "[" + str(ts) + "] — Intervention reprise.")
            append_transition(doc, old, "Intervention en cours", "reprise")
            doc.save(ignore_permissions=True)
            frappe.response["message"] = {
                "ok": 1,
                "title": "INTERVENTION REPRISE",
                "work_seconds": int(doc.get("ss97_work_seconds") or 0),
                "status": "Intervention en cours",
            }
elif action == "admin_clear_security":
    role_rows = frappe.get_all("Has Role", filters={"parent": user, "parenttype": "User"}, fields=["role"], limit_page_length=50)
    role_names = []
    for rr in role_rows:
        role_names.append(rr.role)
    is_admin = ("System Manager" in role_names) or (user == "Administrator")
    if not is_admin:
        frappe.response["message"] = {"ok": 0, "error": "Réservé administrateur", "missing": ["Rôle administrateur requis"]}
    else:
        doc = frappe.get_doc("Issue", issue_name)
        old = doc.get("ss97_ticket_status") or ""
        ts = now_ts()
        doc.ss97_security_suspend = 0
        doc.ss97_security_suspend_motif = (doc.get("ss97_security_suspend_motif") or "") + " | LEVÉE ADMIN " + str(ts)
        doc.ss97_ticket_status = "Intervention en pause"
        doc.status = 'On Hold'
        try:
            doc.ss97_timer_status = "paused"
        except Exception:
            pass
        proof = (doc.get("ss97_proof_log") or "").strip()
        line = "[" + str(ts) + "] — Suspension sécurité LEVÉE par admin " + tech_label(user)
        doc.ss97_proof_log = (proof + "\n" + line).strip() if proof else line
        append_human(doc, line)
        append_transition(doc, old, "Intervention en pause", "levée sécurité admin")
        doc.ss97_client_message = "Le contrôle de sécurité est terminé. Votre technicien peut reprendre sous validation."
        doc.save(ignore_permissions=True)
        frappe.response["message"] = {"ok": 1, "title": "SUSPENSION LEVÉE", "status": "Intervention en pause"}
elif action == "close_remote":
    doc = frappe.get_doc("Issue", issue_name)
    role_rows = frappe.get_all("Has Role", filters={"parent": user, "parenttype": "User"}, fields=["role"], limit_page_length=50)
    role_names = []
    for rr in role_rows:
        role_names.append(rr.role)
    is_admin = ("System Manager" in role_names) or (user == "Administrator")
    is_tech = (doc.get("ss97_technician") or "") == user
    email = frappe.db.get_value("User", user, "email") or user
    is_client = user in [doc.get("raised_by"), doc.get("ss97_contact_email")]
    if not (is_admin or is_tech or is_client):
        frappe.response["message"] = {"ok": 0, "error": "Accès refusé", "missing": ["Non autorisé"]}
    else:
        old_code = doc.get("ss97_remote_session_id") or ""
        ts = now_ts()
        doc.ss97_remote_session_active = 0
        doc.ss97_remote_ended_on = ts
        doc.ss97_remote_session_id = ""
        if (doc.get("ss97_ticket_status") or "") == "Session distante active":
            doc.ss97_ticket_status = "Intervention en cours"
            doc.status = 'Open'
        proof = (doc.get("ss97_proof_log") or "").strip()
        line = "[" + str(ts) + "] — Session distante FERMÉE — code révoqué par " + tech_label(user)
        doc.ss97_proof_log = (proof + "\n" + line).strip() if proof else line
        append_human(doc, line)
        doc.save(ignore_permissions=True)
        frappe.response["message"] = {"ok": 1, "title": "SESSION FERMÉE", "revoked": bool(old_code)}
elif action == "complete":
    if not user or user == "Guest":
        frappe.response["message"] = {"ok": 0, "error": "Session requise", "missing": ["Connexion technicien"]}
    else:
        doc = frappe.get_doc("Issue", issue_name)
        if (doc.get("ss97_technician") or "") != user:
            frappe.response["message"] = {"ok": 0, "error": "Accès refusé", "missing": ["Technicien non affecté"]}
        else:
            miss = []
            if not doc.get("ss97_diagnostic"):
                miss.append("Diagnostic")
            if not doc.get("ss97_intervention_report"):
                miss.append("Rapport d'intervention")
            if doc.get("ss97_remote_session_active"):
                miss.append("Session distante encore active")
            if miss:
                frappe.response["message"] = {"ok": 0, "error": "Données obligatoires manquantes", "missing": miss}
            else:
                ts = now_ts()
                old = doc.get("ss97_ticket_status") or ""
                ws = int(doc.get("ss97_work_seconds") or 0)
                base = doc.get("ss97_timer_resumed_on") or doc.get("ss97_intervention_started_on")
                if base and not doc.get("ss97_pause_started_on"):
                    ws = ws + max(0, int(frappe.utils.time_diff_in_seconds(ts, base) or 0))
                if ws < 1:
                    ws = 1
                dur = int((ws + 59) / 60)
                if dur < 1:
                    dur = 1
                doc.ss97_work_seconds = ws
                doc.ss97_actual_duration_min = dur
                doc.ss97_resolved_on = ts
                doc.ss97_pause_started_on = ""
                doc.ss97_remote_session_active = 0
                try:
                    doc.ss97_resolved_by = user
                except Exception:
                    pass
                try:
                    doc.ss97_timer_status = "stopped"
                except Exception:
                    pass
                subj = str(doc.get("subject") or "") + " " + str(doc.get("name") or "")
                pay = str(doc.get("ss97_payment_status") or "").strip().lower()
                is_test = ("B10 E2E" in subj) or (pay in ("n/a", "na", "test"))
                new_st = "Intervention terminée"
                doc.ss97_ticket_status = new_st
                doc.status = "Resolved"
                line = "[" + str(ts) + "] — Intervention TERMINÉE par " + tech_label(user) + " · durée " + str(dur) + " min · rapport/diagnostic enregistrés"
                append_human(doc, line)
                append_transition(doc, old, new_st, "terminer")
                proof = (doc.get("ss97_proof_log") or "").strip()
                doc.ss97_proof_log = (proof + "\n" + line).strip() if proof else line
                doc.save(ignore_permissions=True)
                notify_gwen("INTERVENTION TERMINÉE", doc.name, new_st)
                frappe.response["message"] = {
                    "ok": 1,
                    "title": "INTERVENTION TERMINÉE",
                    "status": new_st,
                    "resolved_on": ts,
                    "work_seconds": ws,
                    "duration_min": dur,
                    "technician": user,
                }
elif action == "submit_close":
    if not user or user == "Guest":
        frappe.response["message"] = {"ok": 0, "error": "Session requise", "missing": ["Connexion technicien"]}
    else:
        doc = frappe.get_doc("Issue", issue_name)
        if (doc.get("ss97_technician") or "") != user:
            frappe.response["message"] = {"ok": 0, "error": "Accès refusé", "missing": ["Technicien non affecté"]}
        else:
            cur_st = doc.get("ss97_ticket_status") or ""
            if cur_st in ("Clôturé", "Ticket clôturé", "Fermé", "Annulé"):
                frappe.response["message"] = {"ok": 1, "title": "DÉJÀ CLÔTURÉ", "status": cur_st}
            elif cur_st == "Validation administrateur en attente":
                frappe.response["message"] = {"ok": 1, "title": "DÉJÀ SOUMIS", "status": cur_st}
            else:
                miss = []
                if not doc.get("ss97_intervention_report"):
                    miss.append("Rapport d'intervention")
                if not doc.get("ss97_diagnostic"):
                    miss.append("Diagnostic")
                if not doc.get("ss97_checklist_close_done"):
                    miss.append("Checklist de clôture")
                if miss:
                    frappe.response["message"] = {"ok": 0, "error": "Données obligatoires manquantes", "missing": miss}
                else:
                    ts = now_ts()
                    old = cur_st
                    new_st = "Validation administrateur en attente"
                    doc.ss97_ticket_status = new_st
                    doc.status = "Resolved"
                    line = "[" + str(ts) + "] — Soumis à CLÔTURE par " + tech_label(user)
                    append_human(doc, line)
                    append_transition(doc, old, new_st, "soumettre à clôture")
                    proof = (doc.get("ss97_proof_log") or "").strip()
                    doc.ss97_proof_log = (proof + "\n" + line).strip() if proof else line
                    doc.save(ignore_permissions=True)
                    notify_gwen("SOUMIS À CLÔTURE", doc.name, new_st)
                    frappe.response["message"] = {"ok": 1, "title": "TICKET SOUMIS À CLÔTURE", "status": new_st}
elif action == "gwen_emit":
    actv = "TECHNICIEN_CONNECTE"
    st_lab = frappe.db.get_value("Issue", issue_name, "ss97_ticket_status") or ""
    notify_gwen(actv, issue_name, st_lab)
    frappe.response["message"] = {"ok": 1, "ticket": issue_name, "activity": actv}
else:
    frappe.response["message"] = {"ok": 0, "error": "action inconnue", "action": action}
"""


def api_script_source():
    from integrations.ss97_gwen_notifications.wa_block import WA_FUNCS

    return SCRIPT_PREFIX + WA_FUNCS + SCRIPT_BODY


def __getattr__(name):
    if name == "API_SCRIPT":
        return api_script_source()
    raise AttributeError(name)


def server_script_doc():
    return {
        "doctype": "Server Script",
        "name": API_SCRIPT_NAME,
        "script_type": "API",
        "api_method": API_METHOD,
        "allow_guest": 0,
        "disabled": 1,
        "script": api_script_source(),
    }
