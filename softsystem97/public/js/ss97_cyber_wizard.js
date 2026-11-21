/* Progressive, accessible CyberExpert 360 company onboarding.
   Does not send data to external AI or payment providers. */
(() => {
  "use strict";
  function setup() {
    const form = document.getElementById("cyber-request-form");
    if (!form || form.dataset.ss97WizardReady) return;
    const id = (name) => document.getElementById("cyber-" + name);
    const label = (name) => form.querySelector('label[for="cyber-' + name + '"]');
    const consent = id("consent")?.closest("label");
    const groups = [
      ["Entreprise", label("org"), id("org"), id("business-fields")],
      ["Formule", label("kind"), id("kind"), id("offer-fields")],
      ["Autodiagnostic", id("questionnaire")],
      ["Récapitulatif", label("summary"), id("summary"), consent, id("submit")]
    ];
    if (groups.some((group) => group.slice(1).some((item) => !item))) return;
    form.dataset.ss97WizardReady = "1";
    const top = document.createElement("div");
    top.className = "ss97-cyber-wizard-progress";
    top.setAttribute("role", "status");
    top.setAttribute("aria-live", "polite");
    const progressLabel = document.createElement("p");
    const progress = document.createElement("progress");
    progress.setAttribute("aria-label", "Avancement de votre demande");
    top.append(progressLabel, progress);
    form.prepend(top);
    const stages = groups.map((group, i) => {
      const section = document.createElement("section");
      section.className = "ss97-cyber-stage";
      section.dataset.step = String(i);
      const heading = document.createElement("h3");
      heading.textContent = group[0];
      heading.tabIndex = -1;
      section.append(heading);
      group.slice(1).forEach((node) => section.append(node));
      form.append(section);
      return section;
    });
    const summary = document.createElement("div");
    summary.className = "ss97-cyber-summary";
    const summaryTitle = document.createElement("h4");
    summaryTitle.textContent = "Vérifiez vos informations avant l'envoi";
    const detail = document.createElement("dl");
    const disclaimer = document.createElement("p");
    disclaimer.textContent = "Prédiagnostic fondé sur des déclarations, non vérifié par un technicien. " +
      "Aucun scan ni paiement n'est déclenché par l'envoi.";
    summary.append(summaryTitle, detail, disclaimer);
    stages[3].insertBefore(summary, id("submit"));
    const controls = document.createElement("nav");
    controls.className = "ss97-cyber-wizard-nav";
    controls.setAttribute("aria-label", "Navigation du formulaire");
    const back = document.createElement("button");
    back.type = "button";
    back.textContent = "Précédent";
    const forward = document.createElement("button");
    forward.type = "button";
    forward.textContent = "Suivant";
    controls.append(back, forward);
    form.append(controls);
    let active = 0;
    const order = () => id("kind").value === "CYBER" ? [0, 1, 2, 3] : [0, 1, 3];
    function addPair(title, value) {
      const a = document.createElement("dt");
      const b = document.createElement("dd");
      a.textContent = title;
      b.textContent = String(value || "Non renseigné");
      detail.append(a, b);
    }
    function preview() {
      detail.replaceChildren();
      addPair("Entreprise", id("org").value.trim());
      addPair("Type de demande", id("kind").selectedOptions[0]?.textContent);
      if (id("kind").value === "CYBER") {
        addPair("Formule", id("tier").selectedOptions[0]?.textContent);
        addPair("Prix indicatif", id("estimate").textContent);
        addPair("Activité", id("sector").value);
        addPair("Localisation", id("city").value + ", " + id("country").value);
        addPair("Sites et équipements", id("sites").value + " sites, " + id("devices").value + " postes");
        const answers = Array.from(form.querySelectorAll("select[data-question]")).map((el) => el.value);
        if (answers.length && answers.every((v) => ["YES", "PARTIAL", "NO", "UNKNOWN"].includes(v))) {
          const yes = answers.filter((v) => v === "YES").length;
          const partial = answers.filter((v) => v === "PARTIAL").length;
          const unknown = answers.filter((v) => v === "UNKNOWN").length;
          const indicator = Math.round(100 * (2 * yes + partial) / (2 * answers.length));
          addPair("Indicateur déclaratif", indicator + "/100 — non audité");
          addPair("Réponses non confirmées", unknown + " inconnue(s)");
        }
      }
      addPair("Demande", id("summary").value.trim());
    }
    function render(i, focus) {
      active = i;
      const steps = order();
      const position = steps.indexOf(i);
      stages.forEach((stage, index) => { stage.hidden = index !== i; });
      progressLabel.textContent = "Étape " + (position + 1) + " sur " + steps.length + " — " + groups[i][0];
      progress.max = steps.length;
      progress.value = position + 1;
      back.hidden = position === 0;
      forward.hidden = position === steps.length - 1;
      controls.hidden = back.hidden && forward.hidden;
      if (i === 3) preview();
      if (focus) stages[i].querySelector("h3").focus();
    }
    function canAdvance() {
      for (const el of stages[active].querySelectorAll("input,select,textarea")) {
        if (el.disabled || el.closest("[hidden]") || !el.willValidate) continue;
        if (!el.checkValidity()) {
          el.reportValidity();
          return false;
        }
      }
      return true;
    }
    function next() {
      if (!canAdvance()) return;
      const steps = order();
      const following = steps[steps.indexOf(active) + 1];
      if (following !== undefined) render(following, true);
    }
    forward.addEventListener("click", next);
    back.addEventListener("click", () => {
      const steps = order();
      const previous = steps[steps.indexOf(active) - 1];
      if (previous !== undefined) render(previous, true);
    });
    form.addEventListener("input", () => { if (active === 3) preview(); });
    form.addEventListener("change", () => { if (active === 3) preview(); });
    form.addEventListener("reset", () => window.setTimeout(() => render(0, false), 0));
    form.addEventListener("keydown", (event) => {
      if (active !== 3 && event.key === "Enter" && event.target.tagName !== "TEXTAREA") {
        event.preventDefault();
        next();
      }
    });
    form.addEventListener("submit", (event) => {
      if (active !== 3) {
        event.preventDefault();
        event.stopImmediatePropagation();
        next();
      }
    }, true);
    render(0, false);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setup, {once: true});
  } else {
    setup();
  }
})();
