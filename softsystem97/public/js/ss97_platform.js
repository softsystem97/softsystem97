/* SS97 ONE portal — all writes are authorized and validated on the server. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const schema = {
    V2: {title: "text", starts_at: "datetime-local", minutes: "number", instructions: "textarea"},
    V3: {symptoms: "textarea", diagnostic: "textarea", risk: ["low", "medium", "high"]},
    V4: {coordination_note: "textarea", next_step: "text"},
    V5: {category: ["network", "software", "hardware", "access", "other"], urgency: ["normal", "high", "critical"], description: "textarea"},
    V6: {asset_name: "text", asset_type: ["desktop", "laptop", "printer", "server", "network", "other"], asset_tag: "text", inventory_authorized: "checkbox"},
    V7: {asset_record: "text", interval_days: "number", next_due: "date", maintenance_note: "textarea"},
    V8: {specialty: ["systems", "networks", "security", "hardware", "software"], escalation_reason: "textarea", territory: "text"},
    V9: {finding: "textarea", severity: ["low", "medium", "high", "critical"], recommendation: "textarea"},
    V10: {partner_name: "text", offering: "textarea", verification_note: "textarea"},
    V11: {device_alias: "text", display_issue: ["black_screen", "small_image", "blurry", "lag", "other"], resolution_note: "textarea"},
    V12: {symptom_summary: "textarea", affected_component: ["system", "disk", "network", "software", "device", "unknown"], proposed_checks: "textarea"},
    V13: {procedure_name: "text", planned_steps: "textarea", rollback_plan: "textarea", execution_risk: ["low", "medium", "high"]},
    V14: {service_request: ["remote_help", "onsite", "subscription", "quote", "other"], customer_need: "textarea", followup_note: "textarea"},
    V15: {required_skill: ["systems", "networks", "security", "hardware", "software"], dispatch_note: "textarea", territory: "text"},
    V16: {site_alias: "text", health_signal: ["normal", "degraded", "unavailable", "unknown"], observed_at: "datetime-local", observation_note: "textarea"},
    V17: {backup_scope: "text", restore_test_status: ["not_planned", "planned", "passed", "failed"], evidence_note: "textarea", recovery_plan: "textarea"},
    V18: {case_summary: "textarea", suggested_actions: "textarea", human_review: ["pending", "accepted", "rejected"]},
    V19: {organization_type: ["small_business", "company", "municipality", "association", "other"], service_need: "textarea", project_stage: ["discovery", "proposal", "review", "contract"]},
    V20: {metric_type: ["response_time", "resolution_time", "backlog", "satisfaction", "revenue"], source_description: "textarea", validation_note: "textarea"},
  };
  const labels = {
    title: "Mission", starts_at: "Début de mission", minutes: "Durée (minutes)", instructions: "Consignes",
    symptoms: "Symptômes", diagnostic: "Diagnostic humain", risk: "Niveau de risque", coordination_note: "Note de coordination",
    next_step: "Prochaine étape", category: "Catégorie", urgency: "Urgence", description: "Description",
    asset_name: "Nom de l’équipement", asset_type: "Type d’équipement", asset_tag: "Référence interne",
    inventory_authorized: "Autorisation d’inventaire déclarée (à confirmer avec le client)", asset_record: "Identifiant d’un dossier équipement V6",
    interval_days: "Fréquence (jours)", next_due: "Prochaine échéance", maintenance_note: "Consigne de maintenance",
    specialty: "Spécialité recherchée", escalation_reason: "Motif d’escalade", territory: "Zone d’intervention",
    finding: "Constat de cybersécurité", severity: "Gravité", recommendation: "Mesure conseillée",
    partner_name: "Partenaire proposé", offering: "Prestation", verification_note: "Contrôle à effectuer",
    device_alias: "Appareil concerné (nom déclaré)", display_issue: "Défaut d’affichage", resolution_note: "Compte rendu du test humain",
    symptom_summary: "Résumé du problème", affected_component: "Élément concerné", proposed_checks: "Vérifications proposées (non exécutées)",
    procedure_name: "Procédure", planned_steps: "Étapes prévues (non exécutées)", rollback_plan: "Plan de retour arrière", execution_risk: "Risque de la procédure",
    service_request: "Type de demande", customer_need: "Besoin client", followup_note: "Note de suivi",
    required_skill: "Compétence nécessaire", dispatch_note: "Proposition d’affectation (non automatique)",
    site_alias: "Site observé (déclaratif)", health_signal: "État constaté", observed_at: "Date du constat", observation_note: "Note humaine (pas de télémétrie)",
    backup_scope: "Périmètre sauvegarde", restore_test_status: "Résultat déclaré du test", evidence_note: "Preuve humaine à vérifier", recovery_plan: "Plan de reprise",
    case_summary: "Résumé de dossier", suggested_actions: "Suggestions à examiner", human_review: "Décision humaine (pas de moteur IA)",
    organization_type: "Type d’organisme", service_need: "Besoin d’intervention", project_stage: "Étape du projet",
    metric_type: "Indicateur envisagé", source_description: "Source des données à vérifier", validation_note: "Note de validation",
  };
  let serverCatalog = [];
  const status = (value) => { $("platform-status").textContent = value; };

  async function call(method, args, write = false) {
    const url = "/api/method/softsystem97.platform.api." + method;
    const options = write ? {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-Frappe-CSRF-Token": window.frappe?.csrf_token || ""},
      credentials: "same-origin", body: JSON.stringify(args),
    } : {credentials: "same-origin"};
    const target = write ? url : url + "?" + new URLSearchParams(args);
    const response = await fetch(target, options);
    const result = await response.json().catch(() => ({}));
    if (!response.ok || result.exc_type || result.exc) throw new Error("Accès refusé ou données non valides. Vérifiez votre compte et votre ticket.");
    return result.message;
  }

  function renderFields() {
    const version = $("platform-version").value;
    const catalog = serverCatalog.find((item) => item.version === version);
    const root = $("platform-fields");
    root.replaceChildren();
    if (!catalog) return;
    Object.entries(schema[version] || {}).forEach(([key, type]) => {
      const label = document.createElement("label");
      label.htmlFor = "pf-" + key;
      label.textContent = labels[key] || key;
      let input;
      if (Array.isArray(type)) {
        input = document.createElement("select");
        type.forEach((value) => {
          const option = document.createElement("option");
          option.value = value; option.textContent = value; input.append(option);
        });
      } else if (type === "textarea") {
        input = document.createElement("textarea"); input.rows = 3;
      } else {
        input = document.createElement("input"); input.type = type;
        if (type === "number") {input.min = "1"; input.step = "1";}
      }
      input.id = "pf-" + key;
      input.required = catalog.required.includes(key);
      if (input.type === "checkbox") input.setAttribute("aria-label", labels[key]);
      root.append(label, input);
    });
  }

  function availableVersions() {
    const audience = $("platform-audience").value;
    const select = $("platform-version");
    const selected = select.value;
    select.replaceChildren();
    serverCatalog.filter((module) => audience === "technician" || module.version === "V5")
      .forEach((module) => {
        const option = document.createElement("option");
        option.value = module.version;option.textContent = module.version + " — " + module.name;
        select.append(option);
      });
    if (Array.from(select.options).some((option) => option.value === selected)) select.value = selected;
    renderFields();
  }

  function payloadFor(version) {
    const data = {};
    Object.entries(schema[version]).forEach(([key, type]) => {
      const input = $("pf-" + key);
      if (input.type === "checkbox") data[key] = input.checked;
      else if (input.type === "number" && input.value) data[key] = Number(input.value);
      else if (input.type === "datetime-local" && input.value) data[key] = new Date(input.value).toISOString().slice(0, 19) + "Z";
      else if (input.value.trim()) data[key] = input.value.trim();
    });
    return data;
  }

  async function refreshRecords() {
    const ticket = $("platform-ticket").value.trim();
    const audience = $("platform-audience").value;
    if (!ticket) {status("Indiquez d’abord votre numéro de ticket.");return;}
    const root = $("platform-results");
    root.replaceChildren();
    const [data, overview] = await Promise.all([
      call("list_records", {ticket_name: ticket, audience}),
      call("get_case_overview", {ticket_name: ticket, audience}),
    ]);
    const summary = $("platform-overview");
    summary.replaceChildren();
    const paragraph = document.createElement("p");
    paragraph.textContent = "V4 — SS97 ONE : ticket " + overview.ticket_name +
      " (" + overview.ticket_status + ") · " + overview.remote_sessions.length +
      " session(s) V1 répertoriée(s).";
    summary.append(paragraph);
    const counts = document.createElement("p");
    counts.textContent = overview.modules.map((module) => module.version + " : " + module.total).join(" · ");
    summary.append(counts);
    if (!data.records.length) root.textContent = "Aucun dossier pour ce ticket.";
    data.records.forEach((item) => {
      const box = document.createElement("div");box.className = "item";
      const head = document.createElement("strong");
      head.textContent = item.version + " — " + item.title + " (" + item.state + ")";
      const ref = document.createElement("p");ref.textContent = "Référence : " + item.record_id;
      const detail = document.createElement("pre");detail.textContent = JSON.stringify(item.payload, null, 2);
      box.append(head, ref, detail);
      const actions = audience === "technician" ?
        (item.state === "SUBMITTED" ? [["Examiner", "IN_REVIEW"]] :
          item.state === "IN_REVIEW" ? [["Terminer le dossier", "COMPLETED"], ["Annuler", "CANCELLED"]] : []) :
        (item.version === "V5" && item.state === "SUBMITTED" ? [["Annuler ma demande", "CANCELLED"]] : []);
      actions.forEach(([caption, target]) => {
        const button = document.createElement("button");button.type = "button";
        button.className = target === "CANCELLED" ? "danger" : "secondary";
        button.textContent = caption;
        button.addEventListener("click", async () => {
          button.disabled = true;
          try {
            await call("set_record_state", {record_id: item.record_id, state: target, audience}, true);
            await refreshRecords();status("État enregistré et journalisé.");
          } catch (error) {status(error.message);button.disabled = false;}
        });
        box.append(button);
      });
      root.append(box);
    });
  }

  $("platform-version").addEventListener("change", renderFields);
  $("platform-audience").addEventListener("change", availableVersions);
  $("platform-read").addEventListener("click", async () => {
    try {await refreshRecords();status("Liste mise à jour.");} catch (error) {status(error.message);}
  });
  $("platform-create").addEventListener("submit", async (event) => {
    event.preventDefault();
    $("platform-submit").disabled = true;
    try {
      const version = $("platform-version").value;
      await call("create_record", {
        version, ticket_name: $("platform-ticket").value.trim(),
        audience: $("platform-audience").value,
        payload_json: JSON.stringify(payloadFor(version)),
      }, true);
      status("Dossier créé et lié au ticket. Il apparaît dans la liste.");
      await refreshRecords();
    } catch (error) {status(error.message);}
    finally {$("platform-submit").disabled = false;}
  });

  call("get_catalog", {}).then((result) => {
    serverCatalog = result.modules;
    result.modules.forEach((module) => {
      const tile = document.createElement("article");tile.className = "tile";
      const title = document.createElement("strong");title.textContent = module.version + " — " + module.name;
      const note = document.createElement("small");note.textContent = "Dossiers consultables avec ticket autorisé";
      tile.append(title, note);$("platform-tiles").append(tile);
    });
    availableVersions();status("Modules de dossiers chargés. Connexion MeshCentral séparée.");
  }).catch((error) => {status(error.message + " Activation nécessaire sur le site de test.");});
})();
