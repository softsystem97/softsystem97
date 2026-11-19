/* Consistent four-language navigation on all SoftSystem97 technician pages. */
(function () {
  'use strict';
  if (!/^\/espace-technicien(?:\/|$)/.test(location.pathname)) return;
  if (window.__ss97TechnicianLanguageV1) return;
  window.__ss97TechnicianLanguageV1 = true;

  var STORAGE_KEY = 'ss97-technician-language';
  var LANGUAGES = ['fr', 'en', 'es', 'ht'];
  // Keys are stable route identifiers; no client name or case data is translated.
  var labels = {
    dashboard: ['Tableau de bord', 'Dashboard', 'Panel de control', 'Tablo kontwòl'],
    tickets: ['Mes tickets', 'My tickets', 'Mis tickets', 'Tikè mwen yo'],
    intervention: ['Intervention en cours', 'Active intervention', 'Intervención en curso', 'Entèvansyon k ap fèt'],
    'centre-stabilite': ['Centre de stabilité', 'Stability centre', 'Centro de estabilidad', 'Sant estabilite'],
    'boite-a-outils': ['Boîte à outils', 'Toolbox', 'Caja de herramientas', 'Bwat zouti'],
    messages: ['Messages', 'Messages', 'Mensajes', 'Mesaj'],
    agenda: ['Agenda', 'Schedule', 'Agenda', 'Kalandriye'],
    rapports: ["Rapports d'intervention", 'Intervention reports', 'Informes de intervención', 'Rapò entèvansyon'],
    notifications: ['Notifications', 'Notifications', 'Notificaciones', 'Notifikasyon'],
    historique: ['Historique', 'History', 'Historial', 'Istorik'],
    profil: ['Mon profil', 'My profile', 'Mi perfil', 'Pwofil mwen'],
    logout: ['Déconnexion', 'Sign out', 'Cerrar sesión', 'Dekonekte'],
    'status-Disponible': ['Disponible', 'Available', 'Disponible', 'Disponib'],
    'status-Occupé': ['Occupé', 'Busy', 'Ocupado', 'Okipe'],
    'status-En intervention': ['En intervention', 'On a job', 'En intervención', 'Nan entèvansyon'],
    'status-En pause': ['En pause', 'On break', 'En pausa', 'Nan poz'],
    'status-Hors ligne': ['Hors ligne', 'Offline', 'Desconectado', 'Pa konekte'],
    'section-work': ['Espace métier', 'Work area', 'Área de trabajo', 'Espas travay'],
    'heading-dashboard': ['Tableau de bord technicien', 'Technician dashboard', 'Panel del técnico', 'Tablo kontwòl teknisyen'],
    'heading-profil': ['Profil technicien complet', 'Full technician profile', 'Perfil completo del técnico', 'Pwofil teknisyen konplè'],
    'heading-agenda': ['Agenda technicien', 'Technician schedule', 'Agenda del técnico', 'Kalandriye teknisyen'],
    'heading-rapports': ['Rapports', 'Reports', 'Informes', 'Rapò'],
    'heading-messages': ['Messages', 'Messages', 'Mensajes', 'Mesaj'],
    'auth-title': ['Connexion technicien requise', 'Technician sign-in required', 'Inicio de sesión técnico requerido', 'Ou dwe konekte kòm teknisyen'],
    'auth-body': [
      'Cette rubrique est réservée aux techniciens SoftSystem97 actifs. Connectez-vous pour accéder à votre espace personnel.',
      'This area is for active SoftSystem97 technicians. Sign in to access your workspace.',
      'Esta sección es para técnicos activos de SoftSystem97. Inicie sesión para acceder a su espacio.',
      'Espas sa a se pou teknisyen SoftSystem97 ki aktif. Konekte pou antre nan espas pèsonèl ou.'
    ],
    'auth-login': ['Se connecter', 'Sign in', 'Iniciar sesión', 'Konekte'],
    'auth-denied': ['Accès refusé — rôle technicien actif requis.', 'Access denied — an active technician role is required.', 'Acceso denegado: se requiere un rol de técnico activo.', 'Aksè refize — ou bezwen yon wòl teknisyen aktif.'],
    'auth-retry': ['Réessayer', 'Try again', 'Reintentar', 'Eseye ankò'],
    'profile-identity': ['Identité & coordonnées', 'Identity and contact details', 'Identidad y contacto', 'Idantite ak kontak'],
    'profile-skills': ['Compétences & certifications', 'Skills and certifications', 'Competencias y certificaciones', 'Konpetans ak sètifikasyon'],
    'first-name': ['Prénom', 'First name', 'Nombre', 'Non'],
    'last-name': ['Nom', 'Last name', 'Apellido', 'Siyati'],
    'phone': ['Téléphone', 'Phone', 'Teléfono', 'Telefòn'],
    'loading': ['Chargement…', 'Loading…', 'Cargando…', 'Ap chaje…']
  };
  var simpleText = {
    'Identité & coordonnées': 'profile-identity',
    'Compétences & certifications': 'profile-skills',
    'Prénom': 'first-name',
    'Nom': 'last-name',
    'Téléphone': 'phone',
    'Chargement…': 'loading'
  };
  var originals = typeof WeakMap === 'function' ? new WeakMap() : null;

  function supported(value) { return LANGUAGES.indexOf(value) !== -1; }
  function translation(key, lang) {
    var entries = labels[key];
    return entries ? entries[LANGUAGES.indexOf(lang)] : '';
  }
  function writeText(node, key, lang) {
    if (!node) return;
    var result = translation(key, lang);
    if (result && node.textContent !== result) node.textContent = result;
  }
  function selectedLanguage() {
    try {
      var saved = window.localStorage && window.localStorage.getItem(STORAGE_KEY);
      if (supported(saved)) return saved;
    } catch (ignored) { /* Browser may block storage. */ }
    var select = document.getElementById('ss97-ws-lang');
    return select && supported(select.value) ? select.value : 'fr';
  }
  function translate(lang) {
    if (!supported(lang)) lang = 'fr';
    document.documentElement.lang = lang;
    Array.prototype.forEach.call(document.querySelectorAll('.ws-side a[href]'), function (link) {
      var route = (link.getAttribute('href') || '').split('?')[0].split('/').pop();
      var label = link.querySelector('span:last-child');
      writeText(label, route, lang);
    });
    Array.prototype.forEach.call(document.querySelectorAll('.ws-status-btn[data-presence]'), function (button) {
      // Keep data-presence in French: it is a backend state identifier.
      writeText(button, 'status-' + button.getAttribute('data-presence'), lang);
    });
    writeText(document.querySelector('.ws-side-label'), 'section-work', lang);
    var route = location.pathname.split('/').filter(Boolean).pop();
    writeText(document.querySelector('.ws-main h1, main h1.brand'), 'heading-' + route, lang);
    Array.prototype.forEach.call(document.querySelectorAll('[data-tech-login-required]'), function (panel) {
      writeText(panel.querySelector('h3'), 'auth-title', lang);
      writeText(panel.querySelector('p.muted'), 'auth-body', lang);
      writeText(panel.querySelector('[data-ss97-tech-login]'), 'auth-login', lang);
      writeText(panel.querySelector('[data-ss97-tech-retry]'), 'auth-retry', lang);
      var error = panel.querySelector('[data-tech-error]');
      if (error) {
        Array.prototype.forEach.call(error.childNodes, function (node) {
          if (node.nodeType === 3 && node.textContent.trim()) {
            node.textContent = translation('auth-denied', lang) + ' ';
          }
        });
      }
    });
    Array.prototype.forEach.call(document.querySelectorAll('.ws-main h2, .ws-main h3, .ws-main label, .ws-main th, .ws-main .muted'), function (node) {
      if (node.children.length) return;
      var text = node.textContent.trim();
      if (originals && !originals.has(node)) originals.set(node, text);
      var key = simpleText[originals ? originals.get(node) : text];
      if (key) writeText(node, key, lang);
    });
  }
  function boot() {
    var select = document.getElementById('ss97-ws-lang');
    if (!select) return; // Login has its own four-language switcher.
    if (!select.querySelector('option[value="ht"]')) {
      var option = document.createElement('option');
      option.value = 'ht';
      option.textContent = '🇭🇹 HT · Kreyòl ayisyen';
      select.appendChild(option);
    }
    var lang = selectedLanguage();
    select.value = lang;
    translate(lang);
    select.addEventListener('change', function () {
      var next = supported(select.value) ? select.value : 'fr';
      try { if (window.localStorage) window.localStorage.setItem(STORAGE_KEY, next); }
      catch (ignored) { /* Page translation works without persistence. */ }
      translate(next);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
})();
