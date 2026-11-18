/* SS97 TECH OS: presentation only. All authorizations are rechecked on server. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const stateNames = {
    APPLIED: "Candidature reçue", IN_REVIEW: "Étude du dossier",
    EXAM_VALIDATED: "Examen validé", DOCUMENTS_VALIDATED: "Documents vérifiés",
    CONTRACT_SIGNED: "Contrat vérifié", ACTIVE: "Habilitation active",
    SUSPENDED: "Habilitation suspendue", REJECTED: "Candidature non retenue",
    PENDING_APPROVAL: "Validation complémentaire", OFFERED: "Proposée",
    ACCEPTED: "Acceptée", IN_PROGRESS: "En cours",
    REPORT_SUBMITTED: "Rapport transmis", CLIENT_ACCEPTED: "Rapport validé par le client",
    DECLINED: "Déclinée", CANCELLED: "Annulée", DISPUTED: "En discussion",
  };
  let activeExam = null;
  let countdown = null;

  async function api(method, params = {}, write = false) {
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
    if (!response.ok || data.exc || data.exc_type) {
      throw new Error("Opération refusée : compte, habilitation ou données à vérifier.");
    }
    return data.message;
  }

  const status = (message) => {$("tech-status").textContent = message;};
  function addText(parent, tag, value) {
    const el = document.createElement(tag);
    el.textContent = String(value);
    parent.append(el);
    return el;
  }

  function actionButton(parent, label, missionId, nextState) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        let report = "";
        if (nextState === "REPORT_SUBMITTED") {
          report = window.prompt("Compte rendu de l’intervention (sans mot de passe ni secret) :", "") || "";
          if (!report.trim()) {button.disabled = false;return;}
        }
        await api("transition_my_mission", {mission_id: missionId, state: nextState,
          report_summary: report}, true);
        await refresh();
      } catch (error) {status(error.message);button.disabled = false;}
    });
    parent.append(button);
  }

  function renderMissions(missions) {
    const container = $("tech-mission-list");
    container.replaceChildren();
    if (!missions.length) addText(container, "p", "Aucune mission active dans votre spécialité.");
    missions.forEach((mission) => {
      const section = document.createElement("article");
      section.className = "mission";
      addText(section, "h3", "Ticket " + mission.ticket_name);
      addText(section, "p", "État : " + (stateNames[mission.state] || "À vérifier"));
      addText(section, "p", "Rémunération proposée : " + mission.offered_fee_eur + " EUR — aucun paiement programmé");
      if (mission.route_instructions) addText(section, "p", "Fiche de route : " + mission.route_instructions);
      if (mission.report_summary) addText(section, "p", "Rapport : " + mission.report_summary);
      if (mission.state === "OFFERED") {
        actionButton(section, "Accepter", mission.mission_id, "ACCEPTED");
        actionButton(section, "Refuser", mission.mission_id, "DECLINED");
      } else if (mission.state === "ACCEPTED") {
        actionButton(section, "Commencer", mission.mission_id, "IN_PROGRESS");
      } else if (mission.state === "IN_PROGRESS") {
        actionButton(section, "Envoyer mon rapport", mission.mission_id, "REPORT_SUBMITTED");
      }
      container.append(section);
    });
  }

  function stopCountdown() {
    if (countdown !== null) clearInterval(countdown);
    countdown = null;
  }

  function examProgress() {
    if (!activeExam || activeExam.state !== "IN_PROGRESS") return;
    const selected = Object.keys(activeExam.answers || {}).length;
    const remaining = Math.max(0, activeExam.seconds_remaining || 0);
    const minutes = String(Math.floor(remaining / 60)).padStart(2, "0");
    const seconds = String(remaining % 60).padStart(2, "0");
    $("tech-exam-progress").textContent = `${selected}/${activeExam.questions.length} réponses enregistrées · Temps restant : ${minutes}:${seconds}`;
  }

  function showExamResult(data) {
    stopCountdown();
    activeExam = null;
    $("tech-exam-questions").replaceChildren();
    $("tech-exam-submit").hidden = true;
    $("tech-exam-start").hidden = true;
    const label = data.state === "PASSED" ? "Seuil technique atteint" : "Examen non validé";
    $("tech-exam-progress").textContent = `${label} : ${data.correct}/${data.total}. L'habilitation exige toujours une validation humaine.`;
  }

  function renderExam(data) {
    stopCountdown();
    if (data.state !== "IN_PROGRESS") {
      showExamResult(data);
      return;
    }
    activeExam = data;
    $("tech-exam-start").hidden = true;
    $("tech-exam-submit").hidden = false;
    const root = $("tech-exam-questions");
    root.replaceChildren();
    data.questions.forEach((question, index) => {
      const fieldset = document.createElement("fieldset");
      fieldset.className = "mission";
      addText(fieldset, "legend", `${index + 1}. ${question.prompt}`);
      Object.entries(question.options).forEach(([key, label]) => {
        const row = document.createElement("label");
        row.style.display = "block";
        const input = document.createElement("input");
        input.type = "radio";
        input.name = "exam-" + question.id;
        input.value = key;
        input.checked = data.answers?.[question.id] === key;
        input.addEventListener("change", async () => {
          input.disabled = true;
          try {
            await examApi("save_answer", {attempt_id: data.attempt_id,
              question_id: question.id, selected_option: key}, true);
            activeExam.answers[question.id] = key;
            examProgress();
          } catch (error) {status(error.message);input.checked = false;}
          finally {input.disabled = false;}
        });
        row.append(input, document.createTextNode(" " + key + " — " + label));
        fieldset.append(row);
      });
      root.append(fieldset);
    });
    examProgress();
    countdown = setInterval(() => {
      if (!activeExam) return;
      activeExam.seconds_remaining = Math.max(0, activeExam.seconds_remaining - 1);
      examProgress();
      if (activeExam.seconds_remaining === 0) {
        stopCountdown();
        $("tech-exam-submit").disabled = true;
        examApi("submit_exam", {attempt_id: data.attempt_id}, true)
          .then(showExamResult).catch((error) => status(error.message));
      }
    }, 1000);
  }

  async function examApi(method, params = {}, write = false) {
    const url = "/api/method/softsystem97.technician_exams.api." + method;
    const options = {credentials: "same-origin"};
    if (write) {
      options.method = "POST";
      options.headers = {"Content-Type": "application/json",
        "X-Frappe-CSRF-Token": window.frappe?.csrf_token || ""};
      options.body = JSON.stringify(params);
    }
    const response = await fetch(write ? url : url + "?" + new URLSearchParams(params), options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.exc || data.exc_type) {
      throw new Error("Examen indisponible ou session expirée. Contactez l'équipe SS97.");
    }
    return data.message;
  }

  async function refresh() {
    const data = await api("get_my_workspace");
    $("tech-apply").hidden = !!data.profile;
    $("tech-profile").hidden = !data.profile;
    $("tech-exam").hidden = !data.profile || data.profile.state !== "IN_REVIEW";
    $("tech-missions").hidden = !data.profile || data.profile.state !== "ACTIVE";
    if (!data.profile) {
      const select = $("tech-track");
      select.replaceChildren();
      (data.tracks || []).forEach((track) => {
        const option = document.createElement("option");
        option.value = track.code;
        option.textContent = track.label;
        select.append(option);
      });
      status("Vous pouvez déposer votre candidature freelance.");
      return;
    }
    $("tech-track-label").textContent = data.profile.track_label;
    $("tech-profile-state").textContent = stateNames[data.profile.state] || "Contrôle en cours";
    $("tech-profile-help").textContent = data.profile.state === "ACTIVE"
      ? "Votre espace professionnel est limité à cette seule spécialité."
      : "L'équipe SS97 vérifie les étapes nécessaires avant toute activation.";
    renderMissions(data.missions || []);
    status("Espace personnel chargé.");
  }

  $("tech-apply-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.target.querySelector("button");
    button.disabled = true;
    try {await api("apply", {track: $("tech-track").value}, true);await refresh();}
    catch (error) {status(error.message);}
    finally {button.disabled = false;}
  });
  $("tech-exam-start").addEventListener("click", async () => {
    const button = $("tech-exam-start");
    button.disabled = true;
    try {
      const catalog = await examApi("get_catalog");
      if (!catalog.tracks || catalog.tracks.length !== 1) {
        throw new Error("Votre examen n'est pas encore autorisé.");
      }
      const data = await examApi("start_exam", {track: catalog.tracks[0].code}, true);
      renderExam(data);
    } catch (error) {status(error.message);}
    finally {button.disabled = false;}
  });
  $("tech-exam-submit").addEventListener("click", async () => {
    if (!activeExam || !window.confirm("Terminer cet examen et transmettre les réponses ?")) return;
    const button = $("tech-exam-submit");
    button.disabled = true;
    try {
      const result = await examApi("submit_exam", {attempt_id: activeExam.attempt_id}, true);
      showExamResult(result);
    } catch (error) {status(error.message);button.disabled = false;}
  });
  refresh().catch((error) => status(error.message));
})();
