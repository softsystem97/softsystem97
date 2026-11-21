(() => {
  "use strict";
  const result = document.getElementById("admin-bridge-readiness");
  const btn = document.getElementById("admin-bridge-refresh");
  if (!result || !btn) return;
  const labels = {
    tech_os_active:"TECH OS activé",
    exams_service_active:"Service des examens activé",
    bridge_event_schema:"Structure des affectations",
    client_notification_schema:"Structure des notifications client",
    issue_customer_link:"Lien client du ticket ERPNext",
    issue_statuses_match:"États des tickets compatibles",
    no_active_issue_workflow:"Aucun workflow Issue en conflit",
    issue_scripts_inventory_complete:"Inventaire complet des scripts ERPNext Issue",
    issue_scripts_approved:"Versions actives des scripts Issue examinées et approuvées",
    role_configured:"Rôle technicien du pont configuré",
    service_writer_configured:"Compte de service Support Team configuré",
    profile_adapter_confirmed:"Adaptateur de profil validé",
    compatibility_signed_off:"Compatibilité approuvée",
    bridge_enabled:"Pont client–technicien activé",
  };
  async function load() {
    btn.disabled = true;
    result.replaceChildren();
    result.textContent = "Vérification privée en cours…";
    try {
      const url = "/api/method/softsystem97.integrations.ticket_bridge.readiness.get_admin_bridge_preflight";
      const response = await fetch(url, {credentials:"same-origin",cache:"no-store"});
      const body = await response.json().catch(() => ({}));
      if (!response.ok || body.exc || !body.message?.checks) {
        throw Error("Vérification inaccessible : connectez-vous comme responsable habilité.");
      }
      const data = body.message;
      result.replaceChildren();
      const note = document.createElement("p");
      note.textContent = data.activation_prerequisites_met
        ? "Conditions techniques déclarées réunies, recette métier encore obligatoire."
        : "Le pont reste désactivé tant que les prérequis ne sont pas validés.";
      result.append(note);
      const table = document.createElement("ul");
      for (const [key,value] of Object.entries(data.checks)) {
        const li = document.createElement("li");
        li.textContent = (value ? "✓ " : "À résoudre : ") +
          (labels[key] || key);
        table.append(li);
      }
      result.append(table);
      const writers = document.createElement("p");
      writers.textContent = "Comptes de service Support Team possibles : " +
        data.support_writer_candidate_count + " (identités non affichées).";
      result.append(writers);
      const scriptCount = document.createElement("p");
      scriptCount.textContent = "Scripts Issue actifs : " + data.issue_scripts_active_count +
        " · non approuvés/modifiés : " + data.issue_scripts_unapproved_count;
      result.append(scriptCount);
    } catch (error) {result.textContent=error.message;}
    finally {btn.disabled=false;}
  }
  btn.addEventListener("click", load);
  load();
})();
