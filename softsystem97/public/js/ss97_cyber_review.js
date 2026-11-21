/* Auth-aware N4 review display; all mission permissions remain server-side. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const api = "/api/method/softsystem97.cyber_assessment.api.";
  const panel = $("n4-review-panel");
  const box = $("n4-access-guidance");
  function text(parent, tag, value) {
    const child = document.createElement(tag);
    child.textContent = String(value || "");
    parent.append(child);
    return child;
  }
  function guidance(message, destination, label) {
    box.replaceChildren();
    text(box, "p", message);
    if (destination) {
      const link = document.createElement("a");
      link.href = destination;
      link.textContent = label;
      box.append(link);
    }
  }
  async function session() {
    try {
      const response = await fetch("/api/method/frappe.auth.get_logged_user",
        {credentials:"same-origin", cache:"no-store"});
      if (!response.ok) return null;
      const body = await response.json();
      return body.message || null;
    } catch (_) { return null; }
  }
  async function refresh() {
    const root = $("n4-assessments");
    panel.hidden = true;
    box.replaceChildren();
    root.textContent = "Vérification des habilitations et des mandats…";
    try {
      const response = await fetch(api + "get_n4_assessments",
        {credentials:"same-origin",cache:"no-store"});
      if (!response.ok) {
        root.textContent = "Aucun dossier N4 accessible avec cette session.";
        const user = await session();
        if (!user || user === "Guest") {
          guidance("Vous devez d'abord vous connecter avec le compte professionnel du technicien N4.",
            "/login?redirect-to=%2Fss97-cyber-review", "Se connecter comme technicien");
        } else {
          guidance("Le profil N4 CYBER n'est pas actif, ou le module est désactivé, ou aucune mission autorisée n'est accessible. Vérifiez votre candidature, examen, justificatifs, contrat et affectation.",
            "/ss97-tech-os", "Consulter mon profil et mon habilitation");
        }
        return;
      }
      const result = await response.json();
      const docs = result.message?.assessments;
      if (!Array.isArray(docs)) throw Error("Réponse du serveur invalide.");
      root.replaceChildren();
      if (!docs.length) {
        root.textContent = "Aucun dossier N4 autorisé à examiner.";
        guidance("La consultation fonctionne, mais aucune mission avec mandat écrit et rapport soumis n'est prête.",
          "/ss97-tech-cyber","Voir mes missions cyber");
        return;
      }
      docs.forEach(doc => {
        const article = document.createElement("article");
        article.className = "mission";
        text(article,"h3",doc.organization+" — "+doc.ticket);
        text(article,"p","Dossier : "+doc.name+" · "+doc.tier+" · "+doc.state);
        const pdf = document.createElement("a");
        pdf.textContent = "Consulter le PDF déclaratif";
        pdf.href = api+"download_report?assessment_id="+encodeURIComponent(doc.name);
        const select = document.createElement("button");
        select.type = "button";
        select.textContent = "Sélectionner ce dossier";
        select.addEventListener("click",()=>{$("n4-assessment-id").value=doc.name;});
        article.append(pdf,select);
        root.append(article);
      });
      panel.hidden=false;
      guidance("Dossiers autorisés chargés. Les décisions sont revérifiées côté serveur.");
    } catch (error) {
      panel.hidden=true;
      root.textContent="Impossible de charger les dossiers.";
      guidance(error.message,"/ss97-tech-os","Vérifier mon habilitation");
    }
  }
  $("n4-refresh").addEventListener("click",refresh);
  $("n4-review-form").addEventListener("submit",async event=>{
    event.preventDefault();
    if(panel.hidden)return;
    const status=$("n4-review-status");
    status.textContent="Vérification de la décision…";
    try {
      const response=await fetch(api+"review_assessment",{
        method:"POST",credentials:"same-origin",
        headers:{"Content-Type":"application/json",
          "X-Frappe-CSRF-Token":window.frappe?.csrf_token||""},
        body:JSON.stringify({
          assessment_id:$("n4-assessment-id").value,
          decision:$("n4-decision").value,
          review_note:$("n4-note").value,
          evidence_reference:$("n4-evidence").value
        })
      });
      if(!response.ok)throw Error("Décision refusée : mandat, mission ou habilitation à vérifier.");
      const result=(await response.json()).message;
      status.textContent="Décision enregistrée : "+result.state;
      await refresh();
    } catch(error){status.textContent=error.message;}
  });
  refresh();
})();