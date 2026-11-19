/* Passwords stay hidden by default. The user may briefly reveal their own input.
   Never reads, logs, transmits or persists the password value. */
(function () {
  "use strict";

  const processed = new WeakSet();
  let generatedId = 0;

  function hasExistingToggle(field) {
    if (!field.id) return false;
    return Array.from(document.querySelectorAll("button[aria-controls]"))
      .some((button) => button.getAttribute("aria-controls") === field.id);
  }

  function enhance(field) {
    if (processed.has(field)) return;
    processed.add(field);
    if (field.closest("[data-ss97-password-toggle='off']") || hasExistingToggle(field)) return;

    if (!field.id) field.id = "ss97-password-input-" + (++generatedId);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ss97-password-visibility";
    button.textContent = "Afficher le mot de passe";
    button.setAttribute("aria-label", "Afficher le mot de passe temporairement");
    button.setAttribute("aria-controls", field.id);
    button.setAttribute("aria-pressed", "false");
    field.insertAdjacentElement("afterend", button);

    let timeout;
    function hide() {
      clearTimeout(timeout);
      if (field.type !== "password") field.type = "password";
      field.removeAttribute("data-ss97-password-visible");
      button.textContent = "Afficher le mot de passe";
      button.setAttribute("aria-label", "Afficher le mot de passe temporairement");
      button.setAttribute("aria-pressed", "false");
    }

    button.addEventListener("click", function () {
      if (field.type === "text") {
        hide();
        return;
      }
      field.type = "text";
      field.setAttribute("data-ss97-password-visible", "true");
      button.textContent = "Masquer le mot de passe";
      button.setAttribute("aria-label", "Masquer le mot de passe");
      button.setAttribute("aria-pressed", "true");
      clearTimeout(timeout);
      timeout = setTimeout(hide, 10000);
    });

    field.addEventListener("blur", hide);
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) hide();
    });
    field.form?.addEventListener("submit", hide);
  }

  function scan(root) {
    if (root.nodeType === 1 && root.matches("input[type='password']")) enhance(root);
    if (!root.querySelectorAll) return;
    root.querySelectorAll("input[type='password']").forEach(enhance);
  }

  function start() {
    scan(document);
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => mutation.addedNodes.forEach(scan));
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
