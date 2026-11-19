(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const url = "/api/method/softsystem97.cyber_assessment.api.";
  function append(parent, tag, message) {
    const element = document.createElement(tag);
    element.textContent = message;
    parent.append(element);
    return element;
  }
  async function refresh() {
    const root = $("n4-assessments");
    root.textContent = "Vérification des habilitations et des mandats…";
    try {
      const response = await fetch(url + "get_n4_assessments", {credentials: "same-origin"});
      if (!response.ok) throw new Error("Accès N4 refusé ou missions non autorisées.");
      const data = (await response.json()).message;
      root.replaceChildren();
      if (!data.assessments.length) {root.textContent = "Aucun dossier N4 à vérifier.";return;}
      data.assessments.forEach((doc) => {
        const article = document.createElement("article");
        article.className = "mission";
        append(article, "h3", doc.organization + " — " + doc.ticket);
        append(article, "p", "Dossier : " + doc.name + " · " + doc.tier + " · " + doc.state);
        const report = document.createElement("a");
        report.textContent = "Consulter le PDF déclaratif";
        report.href = url + "download_report?assessment_id=" + encodeURIComponent(doc.name);
        const select = document.createElement("button");
        select.type = "button"; select.textContent = "Sélectionner ce dossier";
        select.addEventListener("click", () => {$("n4-assessment-id").value = doc.name;});
        article.append(report, select); root.append(article);
      });
    } catch (error) {root.textContent = error.message;}
  }
  $("n4-refresh").addEventListener("click", refresh);
  $("n4-review-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = $("n4-review-status");
    status.textContent = "Enregistrement sécurisé de la décision…";
    try {
      const response = await fetch(url + "review_assessment", {
        method: "POST", credentials: "same-origin",
        headers: {"Content-Type": "application/json", "X-Frappe-CSRF-Token": window.frappe?.csrf_token || ""},
        body: JSON.stringify({
          assessment_id: $("n4-assessment-id").value,
          decision: $("n4-decision").value,
          review_note: $("n4-note").value,
          evidence_reference: $("n4-evidence").value
        })
      });
      if (!response.ok) throw new Error("Décision refusée. Vérifiez mission, mandat, attribution et habilitation.");
      const data = (await response.json()).message;
      status.textContent = "Décision enregistrée : " + data.state;
      await refresh();
    } catch (error) {status.textContent = error.message;}
  });
  refresh();
})();
