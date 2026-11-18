/* Track-specific workbench; server verifies the same track on page and every API. */
(() => {
  "use strict";
  const root = document.querySelector(".ss97-universe[data-track]");
  if (!root) return;
  const expected = root.dataset.track;
  const $ = (id) => document.getElementById(id);
  const status = (message) => {$("universe-status").textContent = message;};
  const states = {
    PENDING_APPROVAL: "En validation renforcée", OFFERED: "Proposée",
    ACCEPTED: "Acceptée", IN_PROGRESS: "En intervention",
    REPORT_SUBMITTED: "Rapport transmis", CLIENT_ACCEPTED: "Validation client reçue",
    DECLINED: "Refusée", CANCELLED: "Annulée", DISPUTED: "Litige en analyse",
  };
  function textNode(tag, value, parent) {
    const node = document.createElement(tag);
    node.textContent = String(value);
    parent.append(node);
    return node;
  }
  async function api(method, args = {}, write = false) {
    const url = "/api/method/softsystem97.technician_os.api." + method;
    const options = {credentials: "same-origin"};
    if (write) {
      options.method = "POST";
      options.headers = {"Content-Type": "application/json",
        "X-Frappe-CSRF-Token": window.frappe?.csrf_token || ""};
      options.body = JSON.stringify(args);
    }
    const response = await fetch(write ? url : url + "?" + new URLSearchParams(args), options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.exc || data.exc_type) throw new Error("Accès à cette mission refusé ou indisponible.");
    return data.message;
  }
  function button(parent, label, mission, next) {
    const el = document.createElement("button");
    el.type = "button";
    el.textContent = label;
    el.addEventListener("click", async () => {
      el.disabled = true;
      let report = "";
      if (next === "REPORT_SUBMITTED") {
        report = window.prompt("Compte rendu professionnel (sans identifiants ni secrets) :", "") || "";
        if (!report.trim()) {el.disabled = false;return;}
      }
      try {
        await api("transition_my_mission", {mission_id: mission.mission_id,
          state: next, report_summary: report}, true);
        await refresh();
      } catch (error) {status(error.message);el.disabled = false;}
    });
    parent.append(el);
  }
  async function refresh() {
    const data = await api("get_my_workspace");
    if (data.profile?.track !== expected || data.profile?.state !== "ACTIVE") {
      throw new Error("Cette spécialité ne correspond pas à votre habilitation active.");
    }
    const container = $("universe-missions");
    container.replaceChildren();
    if (!data.missions?.length) textNode("p", "Aucune mission autorisée dans cette spécialité.", container);
    for (const mission of (data.missions || [])) {
      if (mission.track !== expected) continue;
      const card = document.createElement("article");
      card.className = "mission";
      textNode("h3", "Ticket " + mission.ticket_name, card);
      textNode("p", "Statut : " + (states[mission.state] || "À vérifier"), card);
      textNode("p", "Rémunération proposée : " + mission.offered_fee_eur + " EUR", card);
      textNode("p", "Paiement : non programmé ; validation financière séparée.", card);
      if (mission.route_instructions) textNode("p", "Fiche de route : " + mission.route_instructions, card);
      if (mission.report_summary) textNode("p", "Rapport : " + mission.report_summary, card);
      if (mission.state === "OFFERED") {
        button(card, "Accepter la mission", mission, "ACCEPTED");
        button(card, "Refuser", mission, "DECLINED");
      } else if (mission.state === "ACCEPTED") {
        button(card, "Démarrer l'intervention", mission, "IN_PROGRESS");
      } else if (mission.state === "IN_PROGRESS") {
        button(card, "Déposer mon compte rendu", mission, "REPORT_SUBMITTED");
      }
      container.append(card);
    }
    status("Espace " + expected + " chargé avec contrôle de votre habilitation.");
  }
  refresh().catch((error) => status(error.message));
})();
