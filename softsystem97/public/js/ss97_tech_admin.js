/* SS97 TECH OS: System Manager dashboard, server-side permission on all calls. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const status = (s) => {$("admin-status").textContent = s;};
  async function api(method, params = {}, write = false) {
    const url = "/api/method/softsystem97.technician_os.api." + method;
    const opt = {credentials: "same-origin"};
    if (write) {
      opt.method = "POST";
      opt.headers = {"Content-Type": "application/json",
        "X-Frappe-CSRF-Token": window.frappe?.csrf_token || ""};
      opt.body = JSON.stringify(params);
    }
    const response = await fetch(write ? url : url + "?" + new URLSearchParams(params), opt);
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.exc || data.exc_type) {
      throw new Error("L'opération a été refusée. Vérifiez le ticket, les rôles, les contrôles et l'étape précédente.");
    }
    return data.message;
  }
  function line(parent, tag, text) {
    const element = document.createElement(tag);
    element.textContent = String(text);
    parent.append(element);
    return element;
  }
  async function refresh() {
    const data = await api("get_admin_overview");
    const summary = $("admin-summary");
    summary.replaceChildren();
    for (const track of ["L2", "BANK", "CYBER"]) {
      const box = document.createElement("div");
      box.className = "tile";
      line(box, "h2", "Techniciens " + track);
      line(box, "p", data.profiles.filter((p) => p.track === track && p.state === "ACTIVE").length + " habilitation(s) actives dans l'échantillon");
      line(box, "p", data.profiles.filter((p) => p.track === track && p.state !== "ACTIVE").length + " autre(s) dossier(s)");
      summary.append(box);
    }
    const profiles = $("admin-profiles");
    profiles.replaceChildren();
    if (!data.profiles.length) line(profiles, "p", "Aucune candidature enregistrée.");
    data.profiles.forEach((profile) => {
      const row = document.createElement("article");
      row.className = "mission";
      line(row, "strong", `${profile.candidate_user} — ${profile.track}`);
      line(row, "p", "État : " + profile.state);
      const button = document.createElement("button");
      button.textContent = "Sélectionner ce profil";
      button.type = "button";
      button.addEventListener("click", () => {
        $("admin-profile-id").value = profile.name;
        $("admin-profile-next").focus();
      });
      row.append(button);
      profiles.append(row);
    });
    const missions = $("admin-missions");
    missions.replaceChildren();
    if (!data.missions.length) line(missions, "p", "Aucune mission enregistrée.");
    data.missions.forEach((mission) => {
      const row = document.createElement("article");
      row.className = "mission";
      line(row, "strong", `${mission.ticket_name} — ${mission.track} — ${mission.technician}`);
      line(row, "p", "État : " + mission.state);
      if (mission.state === "PENDING_APPROVAL") {
        const approve = document.createElement("button");
        approve.type = "button";
        approve.textContent = "Deuxième validation (autre responsable)";
        approve.addEventListener("click", async () => {
          if (!window.confirm("Vous confirmez avoir vérifié l'autorisation écrite et ne pas être le coordinateur initial ?")) return;
          approve.disabled = true;
          try {await api("approve_sensitive_mission", {mission_id: mission.name}, true);await refresh();}
          catch (error) {status(error.message);approve.disabled = false;}
        });
        row.append(approve);
      }
      if (["PENDING_APPROVAL", "OFFERED", "ACCEPTED", "IN_PROGRESS"].includes(mission.state)) {
        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.textContent = "Suspendre / annuler cette mission";
        cancel.addEventListener("click", async () => {
          const reason = window.prompt("Motif obligatoire de l'annulation (sans données privées) :", "") || "";
          if (!reason.trim()) return;
          if (!window.confirm("Annuler cette mission ? Cette action sera journalisée.")) return;
          cancel.disabled = true;
          try {await api("cancel_mission", {mission_id: mission.name, reason}, true);await refresh();}
          catch (error) {status(error.message);cancel.disabled = false;}
        });
        row.append(cancel);
      }
      missions.append(row);
    });
    status("Supervision chargée (maximum " + data.limit + " dossiers par catégorie).");
  }
  $("admin-review-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!window.confirm("Confirmez-vous personnellement cette nouvelle étape de vérification ?")) return;
    const button = event.target.querySelector("button");
    button.disabled = true;
    try {
      await api("review_profile", {profile_id: $("admin-profile-id").value.trim(),
        state: $("admin-profile-next").value,
        evidence_reference: $("admin-evidence").value.trim()}, true);
      $("admin-evidence").value = "";
      await refresh();
    } catch (error) {status(error.message);}
    finally {button.disabled = false;}
  });
  $("admin-mission-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!window.confirm("Envoyer cette proposition au technicien préalablement habilité ?")) return;
    const button = event.target.querySelector("button");
    button.disabled = true;
    try {
      await api("offer_mission", {ticket_name: $("admin-ticket").value.trim(),
        technician_user: $("admin-technician").value.trim(),
        offered_fee_eur: $("admin-fee").value.trim(),
        route_instructions: $("admin-route").value.trim(),
        authorization_reference: $("admin-authorization").value.trim()}, true);
      await refresh();
    } catch (error) {status(error.message);}
    finally {button.disabled = false;}
  });
  refresh().catch((error) => status(error.message));
})();
