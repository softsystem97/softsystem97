(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const status = (message) => {$("cyber-status").textContent = message;};
  const selected = $("cyber-kind");
  const tier = $("cyber-tier");
  const button = $("cyber-submit");
  const values = ["sector", "country", "city", "employees", "sites", "devices", "role", "data-type"];
  const hints = {YES: "Oui", PARTIAL: "Partiellement", NO: "Non", UNKNOWN: "Je ne sais pas"};
  let catalogActive = false;
  let pricesPublished = false;
  let prices = {};
  let questions = [];
  let pendingId = null;
  const idempotency = () => (window.crypto?.randomUUID?.() ||
    (Date.now().toString(36) + Math.random().toString(36).slice(2)));

  function syncForm() {
    const cyber = selected.value === "CYBER";
    $("cyber-offer-fields").hidden = !cyber;
    $("cyber-business-fields").hidden = !cyber;
    $("cyber-questionnaire").hidden = !cyber;
    tier.disabled = !cyber;
    values.forEach((key) => {$("cyber-" + key).required = cyber;});
    $("cyber-questions").querySelectorAll("select").forEach((field) => {
      field.required = cyber;
    });
    const amount = prices[tier.value];
    $("cyber-estimate").textContent = amount ?
      `Estimation automatique : ${amount} EUR HT. Devis et taxes à confirmer, sans paiement.` :
      "Les prix seront affichés après validation de la direction. Aucun montant ne sera prélevé.";
    button.disabled = !catalogActive || (cyber && !pricesPublished);
  }

  selected.addEventListener("change", syncForm);
  tier.addEventListener("change", syncForm);

  function questionUI(question) {
    const root = document.createElement("div");
    root.className = "cyber-question";
    const label = document.createElement("label");
    label.htmlFor = "cyber-q-" + question.code;
    label.textContent = question.label;
    const field = document.createElement("select");
    field.id = label.htmlFor;
    field.dataset.question = question.code;
    field.className = "cyber-answers";
    field.required = true;
    const empty = document.createElement("option");
    empty.value = ""; empty.textContent = "Choisir une réponse";
    field.append(empty);
    Object.entries(hints).forEach(([value, name]) => {
      const option = document.createElement("option");
      option.value = value; option.textContent = name;
      field.append(option);
    });
    root.append(label, field);
    return root;
  }

  async function load() {
    try {
      const resp = await fetch("/api/method/softsystem97.cyber_assessment.api.get_catalog", {
        credentials: "same-origin"
      });
      if (!resp.ok) throw new Error("Catalogue temporairement indisponible.");
      const payload = (await resp.json()).message;
      const root = $("cyber-tiers");
      root.replaceChildren();
      prices = {};
      payload.tiers.forEach((offer) => {
        prices[offer.code] = offer.price_eur;
        const section = document.createElement("article");
        section.className = "panel";
        const h = document.createElement("h2"); h.textContent = offer.label;
        const p = document.createElement("p"); p.textContent = offer.description;
        const price = document.createElement("p");
        price.textContent = offer.price_eur ? offer.price_eur + " EUR HT — estimation" :
          "Tarif à configurer — sans engagement";
        const list = document.createElement("ul");
        offer.checks.forEach((item) => {
          const li = document.createElement("li"); li.textContent = item;
          list.append(li);
        });
        section.append(h, price, p, list); root.append(section);
      });
      questions = payload.questions || [];
      const questionRoot = $("cyber-questions");
      questionRoot.replaceChildren(...questions.map(questionUI));
      pricesPublished = payload.prices_published === true;
      catalogActive = payload.active === true;
      syncForm();
      status(catalogActive ? (pricesPublished ?
        "Les demandes sont ouvertes aux comptes clients connectés ; les devis restent soumis à validation." :
        "Les demandes N2/N3 sont disponibles, mais les tarifs cyber attendent la direction.") :
        "Les offres sont consultables ; la réception des demandes attend sa recette de sécurité.");
    } catch (err) {
      catalogActive = false;
      pricesPublished = false;
      button.disabled = true;
      status(err.message);
    }
  }

  async function refreshReports() {
    const root = $("cyber-my-reports");
    root.textContent = "Chargement de vos expertises…";
    try {
      const response = await fetch("/api/method/softsystem97.cyber_assessment.api.get_my_assessments", {
        credentials: "same-origin"
      });
      if (!response.ok) throw new Error("Connectez-vous avec votre compte client pour consulter vos rapports.");
      const data = (await response.json()).message;
      root.replaceChildren();
      if (!data.assessments?.length) {root.textContent = "Aucune expertise enregistrée sur votre compte.";return;}
      data.assessments.forEach((doc) => {
        const article = document.createElement("article");
        article.className = "mission";
        const text = document.createElement("p");
        const commercial = [doc.quotation && "Devis : " + doc.quotation,
          doc.sales_order && "Commande : " + doc.sales_order,
          doc.sales_invoice && "Facture : " + doc.sales_invoice].filter(Boolean).join(" · ");
        text.textContent = `${doc.ticket} — ${doc.organization} — ${doc.tier} — ${doc.state}` +
          (commercial ? " — " + commercial : " — Devis en attente de traitement");
        const link = document.createElement("a");
        link.href = "/api/method/softsystem97.cyber_assessment.api.download_report?assessment_id=" +
          encodeURIComponent(doc.name);
        link.textContent = "Télécharger le pré-diagnostic / rapport PDF";
        article.append(text, link);
        if (doc.sales_invoice) {
          const pay = document.createElement("button");
          pay.type = "button";
          pay.className = "btn btn-primary";
          pay.textContent = "Payer ma facture avec Stripe";
          pay.addEventListener("click", async () => {
            pay.disabled = true;
            pay.textContent = "Ouverture du paiement…";
            try {
              const response = await fetch(
                "/api/method/softsystem97.cyber_assessment.api.create_assessment_checkout",
                {method: "POST", credentials: "same-origin",
                 headers: {"Content-Type": "application/json",
                   "X-Frappe-CSRF-Token": window.frappe?.csrf_token || ""},
                 body: JSON.stringify({assessment_id: doc.name})}
              );
              const answer = await response.json().catch(() => ({}));
              if (!response.ok || !answer.message?.checkout_url) {
                throw new Error("Paiement indisponible : facture ou autorisation à vérifier.");
              }
              const url = new URL(answer.message.checkout_url);
              if (url.protocol !== "https:" || url.hostname !== "checkout.stripe.com") {
                throw new Error("Adresse de paiement non reconnue.");
              }
              window.location.assign(url.toString());
            } catch (error) {
              const feedback = document.createElement("p");
              feedback.setAttribute("role", "status");
              feedback.textContent = error.message;
              article.append(feedback);
              pay.disabled = false;
              pay.textContent = "Payer ma facture avec Stripe";
            }
          });
          article.append(pay);
        }
        root.append(article);
      });
    } catch (err) {root.textContent = err.message;}
  }

  $("cyber-refresh-reports").addEventListener("click", refreshReports);
  $("cyber-request-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!catalogActive) {
      button.disabled = true;
      status("La réception des demandes cybersécurité n'est pas encore ouverte.");
      return;
    }
    if (selected.value === "CYBER" && !pricesPublished) {
      status("Demande cyber indisponible jusqu'à la publication des tarifs.");
      return;
    }
    button.disabled = true;
    status("Enregistrement du ticket et du dossier en cours…");
    try {
      const cyber = selected.value === "CYBER";
      const profile = cyber ? {
        sector: $("cyber-sector").value, country: $("cyber-country").value,
        city: $("cyber-city").value, employees: $("cyber-employees").value,
        sites: Number($("cyber-sites").value), devices: Number($("cyber-devices").value),
        contact_role: $("cyber-role").value, data_type: $("cyber-data-type").value
      } : null;
      const answers = cyber ? Object.fromEntries(questions.map((question) => [question.code,
        $("cyber-q-" + question.code).value])) : null;
      const data = {
        kind: selected.value, tier: cyber ? tier.value : "",
        organization: $("cyber-org").value, summary: $("cyber-summary").value,
        consent: $("cyber-consent").checked,
        request_id: pendingId || (pendingId = idempotency()), profile, answers
      };
      const resp = await fetch("/api/method/softsystem97.cyber_assessment.api.request_assessment", {
        method: "POST", credentials: "same-origin",
        headers: {"Content-Type": "application/json", "X-Frappe-CSRF-Token": window.frappe?.csrf_token || ""},
        body: JSON.stringify(data)
      });
      const result = await resp.json().catch(() => ({}));
      if (!resp.ok || !result.message?.name) {
        throw new Error("Enregistrement refusé. Vérifiez votre compte client, les tarifs et les autorisations.");
      }
      status("Votre demande " + result.message.name + " a bien été enregistrée. " +
        (result.message.assessment_id ? "Le rapport déclaratif est accessible dans Mes expertises." :
          "Un responsable instruira le ticket."));
      pendingId = null;
      $("cyber-request-form").reset();
      syncForm();
      refreshReports();
    } catch (err) {status(err.message);} finally {button.disabled = !catalogActive;syncForm();}
  });
  // A changed form represents a new request, never a replay of the old one.
  $("cyber-request-form").addEventListener("input", () => {pendingId = null;});
  load();
  refreshReports();
})();
