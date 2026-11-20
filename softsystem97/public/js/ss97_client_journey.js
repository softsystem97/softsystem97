/* Navigation guidée sur les Web Pages existantes — pas de nouveau ticket ni d'accès accordé. */
(function () {
  "use strict";
  var path = window.location.pathname.replace(/\/$/, "");
  if (!["/portail-client", "/ticket-libre", "/ouvrir-ticket/new"].includes(path)) return;

  var copies = {
    fr: {
      eyebrow: "UNE ASSISTANCE QUI VOUS ACCOMPAGNE",
      headline: "Votre problème mérite une réponse claire.",
      intro: "Une seule demande, un suivi dans votre espace, et une intervention organisée avec votre accord.",
      start: "Créer mon ticket", follow: "Suivre mes demandes", account: "Accéder à mon compte",
      stepsTitle: "Comment se déroule votre assistance ?",
      steps: [
        ["Décrivez votre besoin", "Expliquez ce qui ne fonctionne pas, l'appareil concerné et le niveau d'urgence."],
        ["Recevez votre référence", "Après l'enregistrement, conservez le numéro communiqué par le formulaire."],
        ["Retrouvez votre suivi", "Connectez-vous pour consulter les informations accessibles à votre compte."],
        ["Autorisez l'intervention", "Toute assistance à distance exige votre accord préalable pour une session précise."]
      ],
      securityTitle: "Vous gardez le contrôle.",
      security: "Ne transmettez jamais de mot de passe dans le ticket. Aucune prise en main à distance ne commence automatiquement.",
      ticketTitle: "Commençons par votre demande.",
      ticketIntro: "Le ticket libre est ouvert aux personnes qui n'ont pas encore de compte. Pour retrouver plus facilement l'historique, connectez-vous à votre espace client.",
      ticketTips: ["Préparez une description précise et le nom de l'appareil concerné.", "Ajoutez une capture sans mots de passe ni données confidentielles.", "Indiquez quand vous êtes disponible et comment vous joindre."],
      formTitle: "Avant d'envoyer votre ticket", formText: "Décrivez les symptômes, indiquez l'appareil et choisissez une urgence adaptée. N'inscrivez aucun mot de passe ni code bancaire. Une intervention à distance sera proposée séparément, avec votre consentement.",
      formLanguage: "Langues disponibles : français, anglais, espagnol. Pour demander un échange en créole haïtien, choisissez « Autre » et précisez-le dans votre description."
    },
    en: {
      eyebrow: "HELP FROM REAL PEOPLE", headline: "Your problem deserves a clear answer.",
      intro: "One request, updates in your client area, and assistance arranged with your consent.",
      start: "Create my ticket", follow: "Track my requests", account: "Access my account",
      stepsTitle: "How does support work?", steps: [
        ["Describe the issue", "Tell us what is not working, which device is affected, and how urgent it is."],
        ["Get your reference", "After submission, keep the reference shown by the form."],
        ["Follow the progress", "Sign in to view the information available to your account."],
        ["Approve the session", "Remote support always requires your prior approval for a specific session."]
      ], securityTitle: "You remain in control.", security: "Never share passwords in a ticket. Remote access never starts automatically.",
      ticketTitle: "Tell us what you need.", ticketIntro: "You can open a free ticket without an account. Sign in to keep track of your requests.",
      ticketTips: ["Prepare a clear description and device name.", "Attach a screenshot without passwords or private information.", "Tell us when and how to contact you."],
      formTitle: "Before submitting your ticket", formText: "Describe the symptoms, identify the device, and select the right urgency. Do not share passwords or banking codes. Remote assistance needs separate consent.",
      formLanguage: "Available form languages: French, English and Spanish. For Haitian Creole support, choose ‘Other’ and mention it in the description."
    },
    es: {
      eyebrow: "ASISTENCIA CERCANA", headline: "Su problema merece una respuesta clara.",
      intro: "Una sola solicitud, seguimiento desde su espacio y asistencia con su consentimiento.",
      start: "Crear mi ticket", follow: "Seguir mis solicitudes", account: "Entrar en mi cuenta",
      stepsTitle: "¿Cómo funciona la asistencia?", steps: [
        ["Explique el problema", "Indique qué falla, el equipo afectado y la urgencia."],
        ["Reciba una referencia", "Tras el envío, conserve el número que muestre el formulario."],
        ["Siga el proceso", "Acceda a la información disponible en su cuenta."],
        ["Autorice la sesión", "La asistencia remota requiere su permiso previo para cada sesión."]
      ], securityTitle: "Usted mantiene el control.", security: "Nunca comparta contraseñas en el ticket. El acceso remoto no se inicia automáticamente.",
      ticketTitle: "Empecemos con su solicitud.", ticketIntro: "Puede crear un ticket sin cuenta. Inicie sesión para consultar sus solicitudes.",
      ticketTips: ["Prepare una descripción clara y el nombre del equipo.", "Adjunte capturas sin contraseñas ni datos privados.", "Indique cuándo y cómo podemos contactarle."],
      formTitle: "Antes de enviar su ticket", formText: "Describa los síntomas, indique el equipo y seleccione la urgencia. No comparta contraseñas ni códigos bancarios. La asistencia remota requiere autorización aparte.",
      formLanguage: "Idiomas del formulario: francés, inglés y español. Para atención en criollo haitiano, elija ‘Otro’ e indíquelo en la descripción."
    },
    ht: {
      eyebrow: "YON EKIP KI LA POU OU", headline: "Pwoblèm ou merite yon repons ki klè.",
      intro: "Yon sèl demann, swivi nan espas kliyan ou, epi asistans avèk konsantman ou.",
      start: "Kreye tikè mwen", follow: "Swiv demann mwen yo", account: "Antre nan kont mwen",
      stepsTitle: "Kijan asistans lan mache?", steps: [
        ["Eksplike pwoblèm nan", "Di nou sa ki pa mache, ki aparèy ki konsène ak ki jan sa ijan."],
        ["Resevwa referans ou", "Lè ou fin voye demann nan, kenbe nimewo fòm lan ba ou."],
        ["Swiv demann ou", "Konekte pou wè enfòmasyon ki disponib nan kont ou."],
        ["Bay pèmisyon pou sesyon an", "Asistans a distans mande konsantman ou pou chak sesyon."]
      ], securityTitle: "Se ou ki kenbe kontwòl la.", security: "Pa janm bay modpas nan tikè a. Pèsonn pa pran kontwòl òdinatè ou otomatikman.",
      ticketTitle: "Ann kòmanse avèk demann ou.", ticketIntro: "Ou ka ouvri yon tikè san kont. Konekte pou swiv demann ou pi fasil.",
      ticketTips: ["Prepare yon deskripsyon klè ak non aparèy la.", "Ajoute yon foto ekran san modpas ni enfòmasyon prive.", "Di nou kilè ak kijan nou ka kontakte ou."],
      formTitle: "Anvan ou voye tikè a", formText: "Eksplike pwoblèm nan, bay non aparèy la epi chwazi nivo ijans lan. Pa mete modpas ni kòd labank. Asistans a distans mande yon lòt otorizasyon.",
      formLanguage: "Lang fòm lan: franse, anglè ak panyòl. Pou mande asistans an kreyòl ayisyen, chwazi « Autre » epi presize sa nan deskripsyon an."
    }
  };

  var selected = null;
  function lang() {
    var current = document.querySelector('#ss97-lang-nav [aria-current="true"]');
    var code = selected || (current && current.getAttribute("data-ss97-lang")) || document.documentElement.lang || "fr";
    code = code.toLowerCase().split("-")[0];
    return copies[code] ? code : "fr";
  }
  function el(tag, className, parent) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (parent) parent.appendChild(node);
    return node;
  }
  function textNode(tag, parent) { return el(tag, "", parent); }
  function link(parent, href, style) {
    var a = el("a", "ss97-journey-button ss97-journey-button--" + style, parent);
    a.href = href;
    return a;
  }

  function mountPortal() {
    var root = document.querySelector(".ss97-m5");
    var hero = root && root.querySelector(":scope > .hero");
    if (!hero || root.querySelector(".ss97-client-journey")) return null;
    var section = el("section", "ss97-client-journey", null);
    section.setAttribute("data-ss97-no-i18n", "1");
    var eyebrow = textNode("p", section); eyebrow.className = "ss97-journey-eyebrow";
    var title = textNode("h2", section);
    var intro = textNode("p", section); intro.className = "ss97-journey-intro";
    var buttons = el("div", "ss97-journey-actions", section);
    var create = link(buttons, "/ouvrir-ticket/new", "primary");
    var follow = link(buttons, "/espace-client/dashboard", "secondary");
    var account = link(buttons, "/connexion-client", "quiet");
    var stepsTitle = textNode("h3", section);
    var grid = el("div", "ss97-journey-grid", section);
    var steps = Array.from({length: 4}, function (_, index) {
      var card = el("article", "ss97-journey-step", grid);
      var digit = textNode("span", card); digit.className = "ss97-journey-number";
      digit.textContent = String(index + 1).padStart(2, "0");
      return {title: textNode("h4", card), body: textNode("p", card)};
    });
    var safety = el("div", "ss97-journey-safety", section);
    var safetyTitle = textNode("strong", safety);
    var safetyBody = textNode("p", safety);
    hero.insertAdjacentElement("afterend", section);
    return function (t) {
      eyebrow.textContent = t.eyebrow; title.textContent = t.headline; intro.textContent = t.intro;
      create.textContent = t.start; follow.textContent = t.follow; account.textContent = t.account;
      stepsTitle.textContent = t.stepsTitle;
      steps.forEach(function (card, i) { card.title.textContent = t.steps[i][0]; card.body.textContent = t.steps[i][1]; });
      safetyTitle.textContent = t.securityTitle; safetyBody.textContent = t.security;
    };
  }

  function mountTicket() {
    var root = document.querySelector(".ss97-tl");
    var hero = root && root.querySelector(":scope > .hero");
    if (!hero || root.querySelector(".ss97-client-journey")) return null;
    var section = el("section", "ss97-client-journey ss97-client-journey--ticket");
    section.setAttribute("data-ss97-no-i18n", "1");
    var title = textNode("h2", section);
    var intro = textNode("p", section); intro.className = "ss97-journey-intro";
    var list = el("ul", "ss97-journey-tips", section);
    var tips = Array.from({length: 3}, function () { return textNode("li", list); });
    var safety = el("p", "ss97-journey-inline-safety", section);
    hero.insertAdjacentElement("afterend", section);
    return function (t) {
      title.textContent = t.ticketTitle; intro.textContent = t.ticketIntro;
      tips.forEach(function (tip, i) {tip.textContent = t.ticketTips[i];});
      safety.textContent = t.security;
    };
  }

  function mountForm() {
    var heading = Array.from(document.querySelectorAll("h2")).find(function (h) {
      return /Ticket libre/i.test(h.textContent || "");
    });
    if (!heading || document.querySelector(".ss97-client-form-hint")) return null;
    var guide = el("aside", "ss97-client-form-hint");
    guide.setAttribute("data-ss97-no-i18n", "1");
    var title = textNode("h3", guide), desc = textNode("p", guide), langs = textNode("p", guide);
    langs.className = "ss97-journey-form-languages";
    heading.insertAdjacentElement("afterend", guide);
    return function (t) {title.textContent = t.formTitle; desc.textContent = t.formText; langs.textContent = t.formLanguage;};
  }

  function begin() {
    var setup = path === "/portail-client" ? mountPortal : path === "/ticket-libre" ? mountTicket : mountForm;
    var translate = setup();
    if (!translate && window.MutationObserver) {
      var observer = new MutationObserver(function () {
        translate = setup();
        if (translate) {observer.disconnect(); translate(copies[lang()]);}
      });
      observer.observe(document.body, {childList: true, subtree: true});
    }
    if (translate) translate(copies[lang()]);
    document.addEventListener("click", function (event) {
      var button = event.target.closest && event.target.closest('#ss97-lang-nav [data-ss97-lang]');
      if (!button) return;
      selected = button.getAttribute("data-ss97-lang");
      if (translate) translate(copies[lang()]);
      window.requestAnimationFrame(function () { if (translate) translate(copies[lang()]); });
    }, true);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", begin);
  else begin();
})();
