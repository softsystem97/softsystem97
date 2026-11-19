/* Humanise l'accueil public avec les deux membres d'équipe réellement
 * présentés plus bas sur cette même page. Aucun compte n'est modifié. */
(function () {
  "use strict";
  var HOME = "/home";
  if (window.location.pathname.replace(/\/$/, "") !== HOME) return;

  var translations = {
    fr: ["Derrière la technologie, des personnes.", "Une question ?", "Parlons-en", "Une équipe, de vrais échanges", "Nous restons à votre écoute."],
    en: ["Real people behind the technology.", "Have a question?", "Let's talk", "A team, real conversations", "We're here to listen."],
    es: ["Personas reales detrás de la tecnología.", "¿Tiene una pregunta?", "Hablemos", "Un equipo, conversaciones reales", "Estamos aquí para escucharle."],
    ht: ["Gen moun toutbon dèyè teknoloji a.", "Ou gen yon kesyon?", "Ann pale", "Yon ekip, bonjan konvèsasyon", "Nou la pou nou koute ou."]
  };
  var languageLabels = {
    fr: "français · anglais · espagnol · créole haïtien",
    en: "French · English · Spanish · Haitian Creole",
    es: "francés · inglés · español · criollo haitiano",
    ht: "franse · anglè · panyòl · kreyòl ayisyen"
  };
  var chosenLanguage = null;

  function activeLanguage() {
    var active = document.querySelector('#ss97-lang-nav [aria-current="true"]');
    var lang = chosenLanguage || (active && active.getAttribute("data-ss97-lang")) || document.documentElement.lang || "fr";
    lang = lang.toLowerCase().split("-")[0];
    return Object.prototype.hasOwnProperty.call(translations, lang) ? lang : "fr";
  }

  function addPortrait(parent, src, name) {
    var photo = document.createElement("img");
    photo.src = src;
    photo.alt = name;
    photo.width = 45;
    photo.height = 45;
    photo.loading = "lazy";
    photo.decoding = "async";
    parent.appendChild(photo);
  }

  function mount() {
    var actions = document.querySelector(".ss97-accueil .heros .ss-boutons");
    if (!actions || document.querySelector(".ss97-human-note")) return;

    var note = document.createElement("div");
    note.className = "ss97-human-note";
    note.setAttribute("data-ss97-no-i18n", "1");

    var aside = document.querySelector(".ss97-accueil .heros .panneau");
    var spotlight = document.createElement("div");
    spotlight.className = "ss97-human-spotlight";
    spotlight.setAttribute("data-ss97-no-i18n", "1");
    var faces = document.createElement("div");
    faces.className = "ss97-human-faces";
    faces.setAttribute("aria-hidden", "true");
    addPortrait(faces, "/files/jean-claude-moses-ceo-softsystem97.webp", "");
    addPortrait(faces, "/files/nigita-guillaume-communication-linkedin.webp", "");

    var spotlightContent = document.createElement("div");
    spotlightContent.className = "ss97-human-spotlight-content";
    var spotlightHeading = document.createElement("strong");
    var spotlightDetail = document.createElement("span");
    spotlightContent.appendChild(spotlightHeading);
    spotlightContent.appendChild(spotlightDetail);
    spotlight.appendChild(faces);
    spotlight.appendChild(spotlightContent);
    if (aside) aside.insertBefore(spotlight, aside.firstChild);

    var content = document.createElement("div");
    content.className = "ss97-human-note-content";
    var heading = document.createElement("strong");
    var line = document.createElement("span");
    var link = document.createElement("a");
    link.href = "/contact";

    content.appendChild(heading);
    content.appendChild(line);
    line.appendChild(document.createTextNode(" "));
    line.appendChild(link);
    note.appendChild(content);
    actions.insertAdjacentElement("afterend", note);

    function translate() {
      var lang = activeLanguage();
      var copy = translations[lang];
      heading.textContent = copy[0];
      line.firstChild.textContent = copy[1] + " ";
      link.textContent = copy[2];
      spotlightHeading.textContent = copy[3];
      spotlightDetail.textContent = copy[4];
      var listedLanguages = document.querySelectorAll(".ss97-accueil .heros .panneau .ligne")[4];
      var value = listedLanguages && listedLanguages.querySelector("b");
      if (value) {
        value.setAttribute("data-ss97-no-i18n", "1");
        value.textContent = languageLabels[lang];
      }
    }
    translate();
    // Le site insère parfois le sélecteur après DOMContentLoaded et son script
    // de traduction peut mettre à jour aria-current après le clic.
    document.addEventListener("click", function (event) {
      var button = event.target.closest && event.target.closest("#ss97-lang-nav [data-ss97-lang]");
      if (!button) return;
      chosenLanguage = button.getAttribute("data-ss97-lang");
      translate();
      window.requestAnimationFrame(translate);
    }, true);

    if (window.MutationObserver) {
      function observeNavigation() {
        var langNav = document.getElementById("ss97-lang-nav");
        if (!langNav) return false;
        new window.MutationObserver(function () {
          if (!chosenLanguage) translate();
        }).observe(langNav, { subtree: true, attributes: true, attributeFilter: ["aria-current"] });
        if (!chosenLanguage) translate();
        return true;
      }
      if (!observeNavigation()) {
        var waitForNavigation = new window.MutationObserver(function () {
          if (observeNavigation()) waitForNavigation.disconnect();
        });
        waitForNavigation.observe(document.body, { childList: true, subtree: true });
      }
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
  else mount();
})();
