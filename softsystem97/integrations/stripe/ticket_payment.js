/* SS97_SECURE_TICKET_PAYMENT_V1 */
(function () {
  "use strict";
  function mount() {
    if (!window.frappe || !frappe.session || !frappe.session.user || frappe.session.user === "Guest") return;
    var query = new URLSearchParams(location.search);
    var ticket = query.get("ticket") || query.get("name") || "";
    var target = document.getElementById("ticket");
    if (!ticket || !target || document.getElementById("ss97-secure-ticket-payment")) return;
    var panel = document.createElement("section");
    panel.id = "ss97-secure-ticket-payment";
    panel.className = "card";
    var heading = document.createElement("h3");
    heading.textContent = "Règlement de l’intervention";
    var status = document.createElement("p");
    status.setAttribute("aria-live", "polite");
    status.textContent = "Vérification du règlement…";
    var pay = document.createElement("button");
    pay.type = "button";
    pay.className = "btn btn-primary";
    pay.textContent = "Régler ma facture";
    pay.disabled = true;
    var refresh = document.createElement("button");
    refresh.type = "button";
    refresh.className = "btn btn-default";
    refresh.textContent = "Vérifier le paiement";
    panel.appendChild(heading);
    panel.appendChild(status);
    panel.appendChild(pay);
    panel.appendChild(refresh);
    target.insertAdjacentElement("afterend", panel);
    function fail() {
      pay.disabled = true;
      status.textContent = "Paiement indisponible. Contactez l’assistance pour vérifier votre facture.";
    }
    function verify() {
      pay.disabled = true;
      frappe.call({
        method: "softsystem97.integrations.stripe.checkout.get_ticket_payment_status",
        type: "GET", args: {issue: ticket},
        callback: function (r) {
          if (!r || !r.message || typeof r.message.ok !== "boolean") { fail(); return; }
          var confirmed = r.message.ok === true;
          pay.disabled = confirmed;
          status.textContent = confirmed ? "Paiement confirmé." : "Vous pouvez régler la facture associée à ce ticket.";
        }, error: fail
      });
    }
    pay.addEventListener("click", function () {
      if (pay.disabled) return;
      pay.disabled = true;
      status.textContent = "Préparation du paiement…";
      frappe.call({
        method: "softsystem97.integrations.stripe.checkout.create_ticket_checkout",
        type: "POST", args: {issue: ticket},
        callback: function (r) {
          try {
            var url = new URL(r.message.checkout_url);
            if (url.origin !== "https://checkout.stripe.com" || url.username || url.password) { fail(); return; }
            location.assign(url.href);
          } catch (error) { fail(); }
        }, error: fail
      });
    });
    refresh.addEventListener("click", verify);
    window.addEventListener("pageshow", verify);
    verify();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
  else mount();
}());
