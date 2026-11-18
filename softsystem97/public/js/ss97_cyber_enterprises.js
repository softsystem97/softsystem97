(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const status = (message) => {$("cyber-status").textContent = message;};
  const selected = $("cyber-kind");
  const tier = $("cyber-tier");
  const button = $("cyber-submit");
  let catalogActive = false;
  let pendingId = null;
  const idempotency = () => (window.crypto?.randomUUID?.() ||
    (Date.now().toString(36) + Math.random().toString(36).slice(2)));

  selected.addEventListener("change", () => {
    tier.disabled = selected.value === "LIBRE";
  });

  async function load() {
    try {
      const resp = await fetch("/api/method/softsystem97.cyber_assessment.api.get_catalog", {
        credentials: "same-origin"
      });
      if (!resp.ok) throw new Error("Catalogue temporairement indisponible.");
      const payload = (await resp.json()).message;
      const root = $("cyber-tiers");
      root.replaceChildren();
      payload.tiers.forEach((offer) => {
        const section = document.createElement("article");
        section.className = "panel";
        const h = document.createElement("h2"); h.textContent = offer.label;
        const p = document.createElement("p"); p.textContent = offer.description;
        const list = document.createElement("ul");
        offer.checks.forEach((item) => {
          const li = document.createElement("li"); li.textContent = item;
          list.append(li);
        });
        section.append(h, p, list); root.append(section);
      });
      catalogActive = payload.active === true;
      button.disabled = !catalogActive;
      status(catalogActive ? "Les demandes sont ouvertes aux comptes clients connectés." :
        "Les offres sont consultables ; la réception des demandes attend sa recette de sécurité.");
    } catch (err) {catalogActive = false;button.disabled = true;status(err.message);}
  }

  $("cyber-request-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!catalogActive) {
      button.disabled = true;
      status("La réception des demandes cybersécurité n'est pas encore ouverte.");
      return;
    }
    button.disabled = true;
    status("Enregistrement du ticket en cours…");
    try {
      const values = {kind: selected.value, tier: selected.value === "LIBRE" ? "" : tier.value,
        organization: $("cyber-org").value, summary: $("cyber-summary").value,
        consent: $("cyber-consent").checked, request_id: pendingId || (pendingId = idempotency())};
      const resp = await fetch("/api/method/softsystem97.cyber_assessment.api.request_assessment", {
        method: "POST", credentials: "same-origin",
        headers: {"Content-Type": "application/json", "X-Frappe-CSRF-Token": window.frappe?.csrf_token || ""},
        body: JSON.stringify(values)
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data.message?.name) throw new Error("Enregistrement refusé. Vérifiez votre connexion client et réessayez.");
      status("Votre demande " + data.message.name + " a bien été enregistrée. Conservez ce numéro.");
      pendingId = null;
      $("cyber-request-form").reset();
    } catch (err) {status(err.message);} finally {button.disabled = !catalogActive;}
  });
  // A changed form represents a new request, never a replay of the old one.
  $("cyber-request-form").addEventListener("input", () => {pendingId = null;});
  load();
})();
