(() => {
  "use strict";

  const root = document.querySelector(".ss97-universe[data-track='BANK']");
  if (!root) return;

  const section = root.querySelector("#bank-operations");
  const missionSelect = root.querySelector("#bank-mission");
  const form = root.querySelector("#bank-operation-form");
  const fields = root.querySelector("#bank-operation-fields");
  const status = root.querySelector("#bank-operation-status");
  const times = root.querySelector("#bank-operation-times");
  const base = "/api/method/softsystem97.technician_os.bank_operations.";
  let missions = [];
  let current = null;
  let loadNumber = 0;

  async function request(method, args, write = false) {
    const options = {credentials: "same-origin"};
    if (write) {
      options.method = "POST";
      options.headers = {"Content-Type": "application/json",
        "X-Frappe-CSRF-Token": window.frappe?.csrf_token || ""};
      options.body = JSON.stringify(args);
    }
    const url = base + method + (write ? "" : "?" + new URLSearchParams(args));
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok || !data.message) {
      throw new Error("Suivi inaccessible ou données refusées. Rechargez la mission et vérifiez les champs.");
    }
    return data.message;
  }

  function show(record, mission) {
    current = record;
    for (const [key, value] of Object.entries(record.values)) {
      const field = form.elements.namedItem(key);
      if (field) field.value = value;
    }
    const labels = {interrupted_at: "Interruption", resumed_at: "Reprise",
      restored_at: "Rétablissement"};
    times.textContent = Object.entries(labels)
      .filter(([key]) => record[key])
      .map(([key, label]) => label + " · " + record[key]).join("  |  ");
    fields.disabled = mission.state !== "IN_PROGRESS";
    status.textContent = fields.disabled ? "Consultation du suivi de la mission." : "";
    form.hidden = false;
  }

  async function load() {
    const number = ++loadNumber;
    current = null;
    form.hidden = true;
    times.textContent = "";
    const mission = missions.find((item) => item.mission_id === missionSelect.value);
    if (!mission) return;
    status.textContent = "Chargement du suivi…";
    try {
      const record = await request("get_bank_operation", {mission_id: mission.mission_id});
      if (number === loadNumber) show(record, mission);
    } catch (error) {
      if (number === loadNumber) status.textContent = error.message;
    }
  }

  root.addEventListener("ss97-bank-missions", (event) => {
    missions = event.detail.filter((item) => item.track === "BANK");
    const previous = missionSelect.value;
    missionSelect.replaceChildren(...missions.map((mission) => {
      const option = document.createElement("option");
      option.value = mission.mission_id;
      option.textContent = mission.ticket_name;
      return option;
    }));
    if (missions.some((mission) => mission.mission_id === previous)) {
      missionSelect.value = previous;
    }
    section.hidden = !missions.length;
    load();
  });
  missionSelect.addEventListener("change", load);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!current || fields.disabled) return;
    const mission = missions.find((item) => item.mission_id === missionSelect.value);
    if (!mission) return;
    const values = Object.fromEntries(new FormData(form));
    const number = loadNumber;
    fields.disabled = true;
    status.textContent = "Enregistrement…";
    try {
      const record = await request("save_bank_operation",
        {mission_id: mission.mission_id, revision: current.revision, values}, true);
      if (number === loadNumber) {
        show(record, mission);
        status.textContent = "Suivi enregistré.";
      }
    } catch (error) {
      if (number === loadNumber) {
        status.textContent = error.message;
        fields.disabled = false;
      }
    }
  });
})();
