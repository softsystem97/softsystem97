(() => {
  "use strict";
  const $ = (id) => document.getElementById("cyberos-" + id);
  const status = (message) => { $("status").textContent = message; };
  const label = (text) => document.createTextNode(String(text || ""));
  let ready = false;
  const API = "/api/method/softsystem97.cyberos.api.";
  async function call(method, payload) {
    const options = {credentials:"same-origin"};
    if (payload) {
      options.method = "POST";
      options.headers = {"Content-Type":"application/json",
        "X-Frappe-CSRF-Token":window.frappe?.csrf_token || ""};
      options.body = JSON.stringify(payload);
    }
    const response = await fetch(API + method, options);
    const json = await response.json().catch(() => ({}));
    if (!response.ok || json.exc) throw new Error("Action indisponible : accès, données ou configuration à vérifier.");
    return json.message;
  }
  function list(element, rows, formatter) {
    element.replaceChildren();
    if (!rows.length) {
      const li = document.createElement("li");
      li.textContent = "Aucun élément enregistré.";
      element.append(li);
      return;
    }
    rows.forEach((row) => {
      const li = document.createElement("li");
      li.append(label(formatter(row)));
      element.append(li);
    });
  }
  async function refresh() {
    const data = await call("get_my_command_center");
    ready = true;
    $("assets-count").textContent = data.counts.assets;
    $("actions-count").textContent = data.counts.actions_open;
    $("incidents-count").textContent = data.counts.incidents_open;
    list($("assets-list"), data.assets, item =>
      item.label + " · " + item.kind + " · " + item.criticality);
    list($("actions-list"), data.actions, item =>
      item.summary + " · " + item.priority + " · " + item.state);
    Array.from($("actions-list").children).forEach((li, i) => {
      const item = data.actions[i];
      if (!item || item.state === "VERIFIED") return;
      for (const [state, text] of [["IN_PROGRESS", "En cours"], ["DONE_DECLARED", "Déclarer terminée"]]) {
        if (item.state === state) continue;
        const control = document.createElement("button");
        control.type = "button";
        control.textContent = text;
        control.className = "ss97-cyberos-action-control";
        control.addEventListener("click", async () => {
          control.disabled = true;
          try {
            await call("update_my_action", {name: item.name, state});
            await refresh();
          } catch (error) { status(error.message); control.disabled = false; }
        });
        li.append(control);
      }
    });
    list($("incidents-list"), data.incidents, item =>
      item.summary + " · " + item.severity + " · " + item.state);
    status("Espace entreprise chargé. Toutes les données affichées sont déclaratives.");
  }
  function bind(formId, method, fields) {
    const form = $(formId);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!ready || !form.reportValidity()) return;
      const button = form.querySelector("button[type=submit]");
      button.disabled = true;
      status("Enregistrement en cours…");
      try {
        const data = Object.fromEntries(fields.map(field => [field, $(formId + "-" + field).value]));
        if (method === "register_asset") { data.business_service = data.service; delete data.service; }
        const result = await call(method, data);
        form.reset();
        await refresh();
        if (method === "report_incident") status(result.notice);
      } catch (error) { status(error.message); }
      finally { button.disabled = false; }
    });
  }
  bind("asset-form", "register_asset", ["label","kind","criticality","service"]);
  bind("action-form", "create_action", ["summary","category","priority"]);
  bind("incident-form", "report_incident", ["summary","severity","description"]);
  refresh().catch(() => {
    ready = false;
    document.querySelectorAll(".ss97-cyberos form button").forEach(button => {button.disabled = true;});
    status("CyberOS n'est pas encore actif pour ce compte. Vérifiez votre connexion client et la mise en service du serveur.");
  });
})();