"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const script = fs.readFileSync(path.join(__dirname, "../softsystem97/public/js/ss97_human_experience.js"), "utf8");

function element() {
  const node = {
    children: [], attributes: {},
    appendChild(child) { this.children.push(child); return child; },
    insertBefore(child) { this.children.unshift(child); return child; },
    insertAdjacentElement(_pos, child) { this.inserted = child; },
    setAttribute(key, value) { this.attributes[key] = value; },
    getAttribute(key) { return this.attributes[key] ?? null; },
    get firstChild() { return this.children[0]; },
    get textContent() { return this._text ?? this.children.map(x => x.textContent || "").join(""); },
    set textContent(value) { this._text = value; }
  };
  return node;
}

function runHome() {
  const actions = element(), aside = element(), value = element(), nav = element();
  const languageRows = Array.from({ length: 5 }, () => element());
  languageRows[4].querySelector = () => value;
  const clickHandlers = [];
  let active = "fr";
  const document = {
    readyState: "complete", documentElement: { lang: "fr" }, body: element(),
    createElement: element,
    createTextNode: text => ({ textContent: text }),
    getElementById: id => id === "ss97-lang-nav" ? nav : null,
    querySelector(selector) {
      if (selector.includes(".ss-boutons")) return actions;
      if (selector === ".ss97-human-note") return null;
      if (selector.includes(".panneau")) return aside;
      if (selector.includes('aria-current="true"')) return { getAttribute: () => active };
      return null;
    },
    querySelectorAll: () => languageRows,
    addEventListener(type, callback) { if (type === "click") clickHandlers.push(callback); }
  };
  const window = {
    location: { pathname: "/home" },
    requestAnimationFrame: callback => callback(),
    MutationObserver: class { observe() {} disconnect() {} }
  };
  vm.runInNewContext(script, { document, window });
  assert.ok(actions.inserted, "the human message must be rendered on /home");
  assert.ok(aside.children[0], "real team portraits must be rendered on /home");
  assert.match(actions.inserted.textContent, /Derrière la technologie/);
  assert.match(value.textContent, /créole haïtien/);

  for (const [code, expected] of [["en", /Real people/], ["es", /Personas reales/], ["ht", /Gen moun toutbon/]]) {
    active = "fr"; // Simulates the legacy selector temporarily resetting itself.
    clickHandlers[0]({ target: { closest: () => ({ getAttribute: () => code }) } });
    assert.match(actions.inserted.textContent, expected);
    assert.equal(value.textContent.includes(code === "ht" ? "kreyòl ayisyen" : code === "en" ? "Haitian Creole" : "criollo haitiano"), true);
  }
}

function runOutsideHome() {
  let touched = false;
  vm.runInNewContext(script, {
    window: { location: { pathname: "/espace-technicien/dashboard" } },
    document: { querySelector: () => { touched = true; } }
  });
  assert.equal(touched, false, "technician pages must remain untouched");
}

runHome();
runOutsideHome();
console.log("Human homepage and FR/EN/ES/HT checks OK");
