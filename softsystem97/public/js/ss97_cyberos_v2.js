(() => {
  "use strict";
  const $ = (name) => document.getElementById("cyberos-v2-" + name);
  if (!$("status")) return;
  const base = "/api/method/softsystem97.cyberos.advanced_api.";
  let ready = false;
  async function request(method, data) {
    const options = {credentials: "same-origin"};
    if (data) {
      options.method = "POST";
      options.headers = {"Content-Type": "application/json",
                         "X-Frappe-CSRF-Token": window.frappe?.csrf_token || ""};
      options.body = JSON.stringify(data);
    }
    const response = await fetch(base + method, options);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || body.exc) throw new Error("Fonction non disponible ou droits insuffisants.");
    return body.message;
  }
  function rows(node, values, format) {
    node.replaceChildren();
    if (!values.length) {
      const li = document.createElement("li");
      li.textContent = "Aucun élément déclaré.";
      node.append(li);
      return;
    }
    values.forEach(item => {
      const li = document.createElement("li");
      li.textContent = format(item);
      node.append(li);
    });
  }
  function options(id, assets) {
    const select = $(id);
    select.replaceChildren();
    assets.forEach(item => {
      const opt = document.createElement("option");
      opt.value = item.name;
      opt.textContent = item.label + " · " + item.criticality;
      select.append(opt);
    });
  }
  async function reload() {
    const data = await request("get_my_cyberos_v2");
    $("critical").textContent = data.executive.high_criticality_assets;
    $("plans").textContent = data.executive.continuity_plans;
    $("drills").textContent = data.executive.declared_exercises;
    options("source", data.assets);
    options("target", data.assets);
    rows($("dependencies"), data.dependencies, x => x.description + " · " + x.state);
    rows($("plan-list"), data.plans, x => x.service + " · " + x.scenario + " · " + x.state);
    rows($("drill-list"), data.drills, x => x.scenario + " · " + x.state);
    ready = true;
    $("status").textContent = "Modules déclaratifs disponibles. Aucun contrôle réseau n'a été effectué.";
  }
  function bind(formName, method, fields, remap={}) {
    const form = $(formName + "-form");
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (!ready || !form.reportValidity()) return;
      const submit = form.querySelector("button[type=submit]");
      submit.disabled = true;
      try {
        const values = {};
        for (const [target, id] of fields) values[target] = $(id).value;
        await request(method, values);
        form.reset();
        await reload();
      } catch (error) {
        $("status").textContent = error.message;
      } finally {
        submit.disabled = false;
      }
    });
  }
  bind("dependency", "map_dependency", [
    ["source_asset", "source"], ["target_asset", "target"], ["description", "description"]]);
  bind("plan", "create_continuity_plan", [
    ["service", "service"], ["scenario", "scenario"], ["impact", "impact"],
    ["fallback_steps", "fallback"], ["owner_role", "owner"]]);
  bind("drill", "prepare_drill", [
    ["scenario", "drill-scenario"], ["objectives", "objectives"]]);
  reload().catch(() => {
    ready = false;
    document.querySelectorAll("#cyberos-advanced button").forEach(b => { b.disabled = true; });
    $("status").textContent = "Modules en préparation. Connexion client et migration Frappe Cloud nécessaires.";
  });
})();