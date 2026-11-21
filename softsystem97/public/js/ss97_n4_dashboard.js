(() => {
  "use strict";
  const root = document.getElementById("n4-command-center");
  if (!root) return;
  const $ = id => document.getElementById(id);
  const method = "/api/method/softsystem97.technician_os.cyber_dashboard.get_my_n4_dashboard";
  function cell(parent, tag, message) {
    const el = document.createElement(tag);
    el.textContent = String(message || "");
    parent.append(el);
    return el;
  }
  function missions(list) {
    const area = $("n4-command-missions");
    area.replaceChildren();
    if (!list.length) {
      cell(area, "p", "Aucune mission N4 active et autorisée pour ce compte.");
      return;
    }
    for (const mission of list) {
      const article = document.createElement("article");
      article.className = "n4-command-mission";
      cell(article, "h3", "Mission " + mission.ticket_name);
      cell(article, "p", "État : " + mission.state);
      cell(article, "p", "Mandat écrit et deuxième validation : contrôlés.");
      if (mission.route_instructions) cell(article, "p", mission.route_instructions);
      if (mission.report_submitted) cell(article, "p", "Compte rendu déjà transmis.");
      area.append(article);
    }
  }
  function assessments(list) {
    const area = $("n4-command-assessments");
    area.replaceChildren();
    if (!list.length) {
      cell(area, "p", "Aucune expertise autorisée en attente de revue.");
      return;
    }
    for (const item of list) {
      const article = document.createElement("article");
      article.className = "n4-command-mission";
      cell(article, "h3", item.organization);
      cell(article, "p", "Ticket " + item.ticket + " · " + item.tier + " · " + item.state);
      const link = document.createElement("a");
      link.href = "/ss97-cyber-review";
      link.textContent = "Examiner ce dossier dans l'espace de validation";
      article.append(link);
      area.append(article);
    }
  }
  async function refresh() {
    $("n4-command-status").textContent = "Contrôle des habilitations N4 en cours…";
    try {
      const response = await fetch(method, {credentials: "same-origin"});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.exc || !payload.message?.profile) {
        throw Error("Compte N4 non habilité ou module TECH OS non activé.");
      }
      const data = payload.message;
      if (data.profile.track !== "CYBER" || data.profile.state !== "ACTIVE") {
        throw Error("Profil N4 actif obligatoire.");
      }
      $("n4-command-profile").textContent =
        data.profile.track_label + " · " + data.profile.engagement + " · " + data.profile.state;
      for (const key of ["total", "offered", "in_progress", "reports", "closed", "disputed"]) {
        $("n4-command-" + key).textContent = data.summary[key];
      }
      missions(data.missions);
      assessments(data.assessments);
      $("n4-command-status").textContent = "Missions et habilitations personnelles vérifiées.";
    } catch (error) {
      $("n4-command-status").textContent = error.message;
      $("n4-command-profile").textContent = "Accès indisponible";
      $("n4-command-missions").replaceChildren();
      $("n4-command-assessments").replaceChildren();
    }
  }
  $("n4-command-refresh").addEventListener("click", refresh);
  refresh();
})();
