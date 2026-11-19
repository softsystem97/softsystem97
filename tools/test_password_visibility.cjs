// Synthetic DOM smoke test: password contents remain only in the input field.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const script = fs.readFileSync(
  path.join(__dirname, '../softsystem97/public/js/password-visibility.js'), 'utf8'
);

class Element {
  constructor(type) {
    this.nodeType = 1;
    this.type = type;
    this.id = '';
    this.attrs = {};
    this.events = {};
    this.form = null;
    this.value = '';
  }
  closest() { return null; }
  matches(selector) { return selector === "input[type='password']" && this.type === 'password'; }
  querySelectorAll() { return []; }
  setAttribute(name, value) { this.attrs[name] = value; }
  removeAttribute(name) { delete this.attrs[name]; }
  getAttribute(name) { return this.attrs[name] ?? null; }
  insertAdjacentElement(position, element) { assert.equal(position, 'afterend'); this.button = element; }
  addEventListener(name, fn) { this.events[name] = fn; }
}

const password = new Element('password');
password.value = 'Fictional test value, not a credential';
let timerCallback;
const document = {
  readyState: 'complete', nodeType: 9, hidden: false, body: {}, events: {},
  createElement: () => new Element('button'),
  querySelectorAll: (selector) => selector === "input[type='password']" ? [password] : [],
  addEventListener(name, fn) { this.events[name] = fn; },
};
const context = {
  document,
  MutationObserver: class { observe() {} },
  setTimeout(fn) { timerCallback = fn; return 1; },
  clearTimeout() {},
};
vm.runInNewContext(script, context);

const button = password.button;
assert.ok(button, 'revealing button should be created');
assert.equal(password.type, 'password', 'initial input must stay masked');
assert.equal(button.getAttribute('aria-pressed'), 'false');
button.events.click();
assert.equal(password.type, 'text', 'click should reveal input temporarily');
assert.equal(button.getAttribute('aria-pressed'), 'true');
assert.equal(password.value, 'Fictional test value, not a credential');
password.events.blur();
assert.equal(password.type, 'password', 'losing focus must re-mask');
button.events.click();
timerCallback();
assert.equal(password.type, 'password', 'timer must re-mask');
button.events.click();
document.hidden = true;
document.events.visibilitychange();
assert.equal(password.type, 'password', 'backgrounding tab must re-mask');
console.log('Password contrast controls OK');
