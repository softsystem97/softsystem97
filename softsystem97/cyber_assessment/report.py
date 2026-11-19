"""Deterministic, escaped, non-intrusive PDF report for the customer's own dossier."""

from html import escape

from .catalog import ANSWER_LABELS, QUESTIONS, self_assessment


def report_html(doc, profile, answers):
    result = self_assessment(answers)
    h = lambda value: escape(str(value or ""), quote=True)
    answers_rows = "".join(
        f"<tr><td>{h(question)}</td><td>{h(ANSWER_LABELS[answers[key]])}</td></tr>"
        for key, question in QUESTIONS.items()
    )
    strengths = "".join(f"<li>{h(item)}</li>" for item in result["strengths"])
    priorities = "".join(f"<li>{h(item)}</li>" for item in result["priorities"])
    reviewed = doc.state == "APPROVED_N4"
    verdict = ("Relecture humaine N4 effectuée" if reviewed else
               "Pré-diagnostic déclaratif, NON validé par un technicien")
    review = (f"<p><b>Relecteur N4 :</b> {h(doc.reviewed_by)}</p>"
              f"<p><b>Référence du contrôle :</b> {h(doc.evidence_reference)}</p>"
              f"<p><b>Observations :</b> {h(doc.review_note)}</p>") if reviewed else ""
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<style>
body{{font-family:DejaVu Sans,sans-serif;font-size:10pt;color:#18283d}}
h1{{color:#174c70;font-size:21pt}}h2{{color:#174c70;font-size:13pt;margin-top:18px}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:6px;border-bottom:1px solid #c6d6e3;text-align:left}}
.notice{{background:#f0f4f7;padding:12px;border-left:4px solid #a92b3a}}
li{{margin:5px 0}}.small{{font-size:8pt;color:#425367}}
</style></head><body>
<h1>Soft System 97 — CyberExpert 360</h1>
<p><b>Dossier :</b> {h(doc.name)} — <b>Ticket :</b> {h(doc.ticket)}</p>
<p><b>Entreprise :</b> {h(doc.organization)} — <b>Formule :</b> {h(doc.tier)}</p>
<p><b>Prix indicatif HT :</b> {h(doc.price_eur)} EUR — devis/facture distincts requis</p>
<div class="notice"><b>{h(verdict)}</b><p>Indicateur d'autodiagnostic :
{result['score']} / 100 (réponses déclarées par le client, sans vérification technique).
Réponses inconnues : {result['unknown_count']}.</p></div>
<h2>Contexte déclaré</h2>
<p>Activité : {h(profile['sector'])} ; localisation : {h(profile['city'])}, {h(profile['country'])} ;
effectif : {h(profile['employees'])} ; sites : {h(profile['sites'])} ; postes : {h(profile['devices'])}.</p>
<p>Fonction du contact : {h(profile['contact_role'])} ; données : {h(profile['data_type'])}.</p>
<h2>Points forts déclarés</h2><ul>{strengths or '<li>Aucun contrôle confirmé par ce questionnaire.</li>'}</ul>
<h2>Points à examiner en priorité</h2><ul>{priorities or '<li>Demander une vérification indépendante.</li>'}</ul>
<h2>Questionnaire de sécurité</h2><table><thead><tr><th>Domaine</th><th>Réponse déclarée</th></tr></thead>
<tbody>{answers_rows}</tbody></table>
<h2>Revue N4</h2>{review or '<p>En attente de revue humaine N4.</p>'}
<p class="small">Ce document n'est ni un audit certifié, ni un résultat de scan, ni une preuve
d'absence de vulnérabilités. Tout test actif ou accès distant exige un mandat distinct et un
consentement explicite. Il ne constitue pas un devis accepté ou un paiement.</p>
</body></html>"""
