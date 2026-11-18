/* SS97 customer report review: ticket ownership and roles enforced on server. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const status = (message) => {$("ss97-client-mission-status").textContent = message;};
  const labels = {
    PENDING_APPROVAL: "Validation supplémentaire en attente",
    OFFERED: "Proposition envoyée au technicien",
    ACCEPTED: "Mission acceptée", IN_PROGRESS: "Intervention en cours",
    REPORT_SUBMITTED: "Rapport en attente de votre réponse",
    CLIENT_ACCEPTED: "Rapport accepté", DISPUTED: "Rapport contesté",
    DECLINED: "Mission refusée", CANCELLED: "Mission annulée",
  };
  let currentTicket = "";

  async function api(method, params, write = false) {
    const url = "/api/method/softsystem97.technician_os.api." + method;
    const options = {credentials: "same-origin"};
    if (write) {
      options.method = "POST";
      options.headers = {"Content-Type": "application/json",
        "X-Frappe-CSRF-Token": window.frappe?.csrf_token || ""};
      options.body = JSON.stringify(params);
    }
    const response = await fetch(write ? url : url + "?" + new URLSearchParams(params), options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.exc || data.exc_type || !data.message) {
      throw new Error("Ticket inaccessible ou intervention non disponible pour ce compte.");
    }
    return data.message;
  }

  function text(parent, tag, value) {
    const element = document.createElement(tag);
    element.textContent = String(value);
    parent.append(element);
    return element;
  }

  function action(parent, mission, decision) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = decision === "CLIENT_ACCEPTED" ? "Accepter ce rapport" : "Contester ce rapport";
    button.addEventListener("click", async () => {
      const prompt = decision === "CLIENT_ACCEPTED"
        ? "Confirmez-vous la réception et l'acceptation du rapport d'intervention ?"
        : "Voulez-vous contester ce rapport ? L'équipe SS97 devra reprendre votre dossier.";
      if (!window.confirm(prompt)) return;
      button.disabled = true;
      try {
        await api("review_client_report", {mission_id: mission.mission_id, decision}, true);
        await load(currentTicket);
        status(decision === "CLIENT_ACCEPTED" ? "Rapport accepté et enregistré." : "Contestation enregistrée.");
      } catch (error) {status(error.message);button.disabled = false;}
    });
    parent.append(button);
  }

  function render(missions) {
    const root = $("ss97-client-mission-results");
    root.replaceChildren();
    if (!missions.length) {
      text(root, "p", "Aucune intervention TECH OS liée à ce ticket pour le moment.");
      return;
    }
    missions.forEach((mission) => {
      const section = document.createElement("article");
      section.className = "mission";
      text(section, "h3", "Intervention " + mission.mission_id);
      text(section, "p", "État : " + (labels[mission.state] || "En vérification"));
      if (mission.report_summary) text(section, "p", "Compte rendu : " + mission.report_summary);
      if (mission.state === "REPORT_SUBMITTED") {
        action(section, mission, "CLIENT_ACCEPTED");
        action(section, mission, "DISPUTED");
      }
      root.append(section);
    });
  }

  async function load(ticketName) {
    const data = await api("get_client_missions", {ticket_name: ticketName});
    currentTicket = ticketName;
    render(data.missions || []);
    status("Interventions du ticket " + ticketName + " chargées.");
  }

  $("ss97-client-mission-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const ticketName = $("ss97-client-ticket").value.trim();
    if (!ticketName || ticketName.length > 140) return;
    const button = event.target.querySelector("button");
    button.disabled = true;
    $("ss97-client-mission-results").replaceChildren();
    status("Vérification de votre ticket…");
    try {await load(ticketName);}
    catch (error) {status(error.message);}
    finally {button.disabled = false;}
  });
  const suggested = new URLSearchParams(window.location.search).get("ticket") || "";
  if (suggested && suggested.length <= 140) $("ss97-client-ticket").value = suggested;
})();
