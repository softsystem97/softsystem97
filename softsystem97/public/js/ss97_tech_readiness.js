/* Read-only, System Manager-only go-live checks; never toggles feature flags. */
(() => {
  "use strict";
  const root = document.getElementById("readiness-results");
  const refresh = document.getElementById("readiness-refresh");

  function row(list, label, okay, note) {
    const item = document.createElement("li");
    item.textContent = `${okay ? "✓" : "À vérifier"} — ${label}${note ? " : " + note : ""}`;
    list.append(item);
  }

  async function load() {
    refresh.disabled = true;
    root.textContent = "Contrôle de la configuration en cours…";
    try {
      const response = await fetch(
        "/api/method/softsystem97.cyber_assessment.api.get_admin_readiness",
        {credentials: "same-origin"}
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.exc || payload.exc_type || !payload.message) {
        throw new Error("Accès refusé ou contrôles indisponibles.");
      }
      const data = payload.message;
      const list = document.createElement("ul");
      row(list, "Espace TECH OS", data.tech_os_enabled, data.tech_os_enabled ? "activé" : "désactivé par sécurité");
      row(list, "Structures techniciens", data.technician_schema_ready, data.technician_schema_ready ? "présentes" : "migration manquante");
      row(list, "Structures d'examens", data.exam_schema_ready, data.exam_schema_ready ? "présentes" : "migration manquante");
      row(list, "Examens", data.exams_enabled, data.exams_enabled ? "activés" : "désactivés");
      row(list, "Emails du parcours technicien", data.technician_email_enabled,
        data.technician_email_enabled ? "option activée, réception non vérifiée" : "retenus jusqu'au test SMTP");
      row(list, "Pont client / tickets", data.ticket_bridge_enabled, data.ticket_bridge_enabled ? "configuré" : "désactivé");
      row(list, "Emails des tickets", data.ticket_email_enabled, data.ticket_email_enabled ? "option active, livraison non vérifiée" : "désactivés");
      row(list, "Accueil des demandes cyber", data.cyber_intake_enabled, data.cyber_intake_enabled ? "activé" : "désactivé");
      row(list, "Notifications client", data.client_notification_doctype, data.client_notification_doctype ? "structure présente" : "structure absente");
      for (const [label, current, target] of [
        ["N2 généraliste", data.n2_question_count, 20],
        ["N3 bancaire", data.n3_question_count, 30],
        ["N4 cybersécurité", data.n4_question_count, 40]
      ]) {
        const number = Number.isFinite(Number(current)) ? Number(current) : 0;
        row(list, `Banque de questions ${label}`, number >= target, `${number}/${target} questions actives`);
      }
      root.replaceChildren(list);
    } catch (error) {
      root.textContent = error.message;
    } finally {
      refresh.disabled = false;
    }
  }

  refresh.addEventListener("click", load);
  load();
})();
