(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  async function api(method) {
    const response = await fetch("/api/method/softsystem97.cyber_assessment.api." + method, {
      credentials: "same-origin"});
    if (!response.ok) throw new Error("Contrôles indisponibles ou autorisation insuffisante.");
    return (await response.json()).message;
  }
  function addText(parent, tag, label) {
    const el = document.createElement(tag); el.textContent = String(label);
    parent.append(el); return el;
  }
  async function checkReadiness() {
    const root = $("admin-readiness");
    try {
      const data = await api("get_admin_readiness");
      const tests = [
        ["TECH OS", data.tech_os_enabled],
        ["Banque d'examens", data.exams_enabled],
        ["Pont de tickets", data.ticket_bridge_enabled],
        ["File d'emails", data.ticket_email_enabled],
        ["Accueil demandes cyber", data.cyber_intake_enabled],
        ["Notifications client", data.client_notification_doctype],
        ["Questions N2 : " + data.n2_question_count + "/20", data.n2_question_count >= 20],
        ["Questions N3 : " + data.n3_question_count + "/30", data.n3_question_count >= 30],
        ["Questions N4 : " + data.n4_question_count + "/40", data.n4_question_count >= 40]
      ];
      root.replaceChildren();
      const list = document.createElement("ul");
      tests.forEach(([label, okay]) => addText(list, "li", (okay ? "✓ " : "À configurer : ") + label));
      root.append(list);
    } catch (err) {root.textContent = err.message;}
  }
  async function checkQueue() {
    const root = $("admin-cyber-queue");
    try {
      const result = await api("get_admin_queue");
      root.replaceChildren();
      if (!result.tickets.length) {addText(root, "p", "Aucune demande cyber dans la file.");return;}
      result.tickets.forEach((ticket) => {
        const article = document.createElement("article"); article.className = "mission";
        addText(article, "h3", ticket.name + " · " + ticket.status);
        addText(article, "p", ticket.subject);
        addText(article, "p", "Client : " + ticket.customer);
        root.append(article);
      });
    } catch (err) {root.textContent = err.message;}
  }
  Promise.all([checkReadiness(), checkQueue()]);
})();
