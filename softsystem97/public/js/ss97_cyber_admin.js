(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  async function api(method) {
    const response = await fetch("/api/method/softsystem97.cyber_assessment.api." + method, {
      credentials: "same-origin"});
    if (!response.ok) throw new Error("Contrôles indisponibles ou autorisation insuffisante.");
    return (await response.json()).message;
  }
  function addText(parent, tag, label) {
    const el = document.createElement(tag); el.textContent = String(label);
    parent.append(el); return el;
  }
  async function checkReadiness() {
    const root = $("admin-readiness");
    try {
      const data = await api("get_admin_readiness");
      const tests = [
        ["TECH OS", data.tech_os_enabled],
        ["Banque d'examens", data.exams_enabled],
        ["Pont de tickets", data.ticket_bridge_enabled],
        ["File d'emails", data.ticket_email_enabled],
        ["Accueil demandes cyber", data.cyber_intake_enabled],
        ["Dossiers d'expertise migrés", data.cyber_schema_ready],
        ["Tarification cyber publiée", data.cyber_prices_published],
        ["Analyse OpenAI", data.cyber_openai_connected],
        ["Notifications client", data.client_notification_doctype],
        ["Questions N2 : " + data.n2_question_count + "/20", data.n2_question_count >= 20],
        ["Questions N3 : " + data.n3_question_count + "/30", data.n3_question_count >= 30],
        ["Questions N4 : " + data.n4_question_count + "/40", data.n4_question_count >= 40]
      ];
      root.replaceChildren();
      const list = document.createElement("ul");
      tests.forEach(([label, okay]) => addText(list, "li", (okay ? "✓ " : "À configurer : ") + label));
      root.append(list);
    } catch (err) {root.textContent = err.message;}
  }
  async function checkQueue() {
    const root = $("admin-cyber-queue");
    try {
      const result = await api("get_admin_queue");
      root.replaceChildren();
      if (!result.tickets.length) {addText(root, "p", "Aucune demande cyber dans la file.");return;}
      result.tickets.forEach((ticket) => {
        const article = document.createElement("article"); article.className = "mission";
        addText(article, "h3", ticket.name + " · " + ticket.status);
        addText(article, "p", ticket.subject);
        addText(article, "p", "Client : " + ticket.customer);
        if (ticket.assessment_id) {
          addText(article, "p", "Dossier expertise : " + ticket.assessment_id);
          const select = document.createElement("button");
          select.type = "button";
          select.textContent = "Raccorder une commande à ce dossier";
          select.addEventListener("click", () => {
            $("admin-cyber-assessment-id").value = ticket.assessment_id;
            $("admin-cyber-document-name").focus();
          });
          article.append(select);
        }
        root.append(article);
      });
    } catch (err) {root.textContent = err.message;}
  }
  const pricing = $("admin-cyber-pricing-form");
  async function checkPricing() {
    const status = $("admin-cyber-pricing-status");
    if (!pricing) return;
    try {
      const data = await api("get_admin_pricing");
      $("admin-cyber-basique").value = data.basique_eur;
      $("admin-cyber-premium").value = data.premium_eur;
      $("admin-cyber-ultra").value = data.ultra_eur;
      $("admin-cyber-publish").checked = data.is_published;
      status.textContent = data.is_published ? "Tarifs indicatifs publiés." :
        "Tarifs non publiés. Aucune demande cyber tarifée n'est ouverte.";
    } catch (err) {status.textContent = err.message;}
  }
  if (pricing) pricing.addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = $("admin-cyber-pricing-status");
    status.textContent = "Contrôle et enregistrement…";
    try {
      const response = await fetch(
        "/api/method/softsystem97.cyber_assessment.api.set_admin_pricing", {
        method: "POST", credentials: "same-origin",
        headers: {"Content-Type": "application/json",
          "X-Frappe-CSRF-Token": window.frappe?.csrf_token || ""},
        body: JSON.stringify({
          basique_eur: $("admin-cyber-basique").value,
          premium_eur: $("admin-cyber-premium").value,
          ultra_eur: $("admin-cyber-ultra").value,
          publish: $("admin-cyber-publish").checked
        })
      });
      if (!response.ok) throw new Error("Tarifs refusés. Vérifiez vos droits et les montants.");
      status.textContent = "Tarifs enregistrés par la direction. La réception des demandes doit être activée séparément.";
      await checkReadiness();
    } catch (err) {status.textContent = err.message;}
  });
  const commercial = $("admin-cyber-commercial-form");
  if (commercial) commercial.addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = $("admin-cyber-commercial-status");
    status.textContent = "Vérification du client et du document…";
    try {
      const response = await fetch(
        "/api/method/softsystem97.cyber_assessment.api.link_commercial_document", {
        method: "POST", credentials: "same-origin",
        headers: {"Content-Type": "application/json",
          "X-Frappe-CSRF-Token": window.frappe?.csrf_token || ""},
        body: JSON.stringify({
          assessment_id: $("admin-cyber-assessment-id").value,
          document_type: $("admin-cyber-document-type").value,
          document_name: $("admin-cyber-document-name").value
        })
      });
      if (!response.ok) throw new Error("Raccordement refusé : document inexistant, annulé ou client différent.");
      status.textContent = "Document commercial rattaché au dossier, sans paiement automatique.";
    } catch (err) {status.textContent = err.message;}
  });
  Promise.all([checkReadiness(), checkQueue(), checkPricing()]);
})();
