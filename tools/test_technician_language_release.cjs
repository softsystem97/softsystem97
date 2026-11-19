'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const code = fs.readFileSync(path.resolve(__dirname, '../softsystem97/public/js/technician_language.js'), 'utf8');

function textNode(value) { return {textContent: value, children: []}; }

function fixture(route, store, withSelect = true) {
  const navLabel = textNode('Rapports d\'intervention');
  const link = {
    getAttribute() { return '/espace-technicien/rapports'; },
    querySelector() { return navLabel; }
  };
  const status = {
    textContent: 'En intervention',
    getAttribute() { return 'En intervention'; }
  };
  const heading = textNode('Profil technicien complet');
  const section = textNode('Espace métier');
  const authTitle = textNode('Connexion technicien requise');
  const authBody = textNode('Cette rubrique est réservée aux techniciens SoftSystem97 actifs. Connectez-vous pour accéder à votre espace personnel.');
  const login = textNode('Se connecter');
  const retry = textNode('Réessayer');
  const errorText = {nodeType: 3, textContent: 'Accès refusé — rôle technicien actif requis. '};
  const panel = {
    querySelector(selector) {
      return {'h3': authTitle, 'p.muted': authBody, '[data-ss97-tech-login]': login,
        '[data-ss97-tech-retry]': retry, '[data-tech-error]': {childNodes: [errorText]}}[selector];
    }
  };
  const options = [];
  const listeners = {};
  const select = withSelect ? {
    value: 'fr',
    appendChild(option) { options.push(option); },
    querySelector(selector) { return options.find(o => selector === 'option[value="ht"]' && o.value === 'ht'); },
    addEventListener(name, handler) {listeners[name] = handler;}
  } : null;
  const document = {
    readyState: 'complete', documentElement: {lang: 'fr'},
    getElementById(id) { return id === 'ss97-ws-lang' ? select : null; },
    createElement() { return {}; },
    querySelector(selector) {
      return {
        '.ws-side-label': section,
        '.ws-main h1, main h1.brand': heading
      }[selector] || null;
    },
    querySelectorAll(selector) {
      return {
        '.ws-side a[href]': [link],
        '.ws-status-btn[data-presence]': [status],
        '[data-tech-login-required]': [panel],
        '.ws-main h2, .ws-main h3, .ws-main label, .ws-main th, .ws-main .muted': []
      }[selector] || [];
    }
  };
  const storage = {
    getItem(key) { return store.get(key) || null; },
    setItem(key, value) { store.set(key, value); }
  };
  const window = {localStorage: storage};
  vm.runInNewContext(code, {location: {pathname: '/espace-technicien/' + route}, document, window});
  return {document, select, listeners, options, navLabel, status, heading, section,
    authTitle, authBody, login, retry, errorText};
}

const store = new Map();
const profile = fixture('profil', store);
assert.equal(profile.options.length, 1, 'add one Haitian Creole option');
assert.equal(profile.options[0].value, 'ht');
assert.match(profile.options[0].textContent, /HT.*Kreyòl/);
profile.select.value = 'ht';
profile.listeners.change();
assert.equal(profile.document.documentElement.lang, 'ht');
assert.equal(profile.navLabel.textContent, 'Rapò entèvansyon');
assert.equal(profile.status.textContent, 'Nan entèvansyon');
assert.equal(profile.heading.textContent, 'Pwofil teknisyen konplè');
assert.equal(profile.section.textContent, 'Espas travay');
assert.equal(profile.authTitle.textContent, 'Ou dwe konekte kòm teknisyen');
assert.equal(profile.authBody.textContent, 'Espas sa a se pou teknisyen SoftSystem97 ki aktif. Konekte pou antre nan espas pèsonèl ou.');
assert.equal(profile.login.textContent, 'Konekte');
assert.equal(profile.retry.textContent, 'Eseye ankò');
assert.match(profile.errorText.textContent, /^Aksè refize/);
assert.equal(store.get('ss97-technician-language'), 'ht');

const nextPage = fixture('agenda', store);
assert.equal(nextPage.select.value, 'ht', 'language persists across routes');
assert.equal(nextPage.heading.textContent, 'Kalandriye teknisyen');
nextPage.select.value = 'en';
nextPage.listeners.change();
assert.equal(nextPage.navLabel.textContent, 'Intervention reports');
assert.equal(nextPage.authTitle.textContent, 'Technician sign-in required');
assert.equal(store.get('ss97-technician-language'), 'en');
nextPage.select.value = 'fr';
nextPage.listeners.change();
assert.equal(nextPage.heading.textContent, 'Agenda technicien');

const loginPage = fixture('login', store, false);
assert.equal(loginPage.select, null, 'the login screen retains its own language switcher');
console.log('4 technician translation adapter checks passed');
