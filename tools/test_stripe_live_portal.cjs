/* Browser behavior for the production addon; no network, payment, or real data. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('softsystem97/integrations/stripe/ticket_payment.js', 'utf8');

function page({verified = false, failure = false, user = 'client@example.invalid', url = 'https://checkout.stripe.com/c/pay/fixture'} = {}) {
  const elements = [], calls = [], navigations = [];
  function element(tag) {
    const el = {tag, children: [], listeners: {}, disabled: false,
      appendChild(child) { this.children.push(child); }, setAttribute() {},
      insertAdjacentElement(position, child) { this.children.push(child); },
      addEventListener(name, action) { this.listeners[name] = action; }};
    elements.push(el);
    return el;
  }
  element('div').id = 'ticket';
  const document = {readyState: 'complete', createElement: element,
    getElementById(id) { return elements.find(el => el.id === id); }};
  const frappe = {session: {user}, call(request) {
    calls.push(request);
    if (request.method.endsWith('get_ticket_payment_status')) {
      if (failure) request.error();
      else request.callback({message: {ok: verified}});
    } else request.callback({message: {checkout_url: url}});
  }};
  const location = {search: '?ticket=ISSUE-OWN&paid=1&amount=1&session_id=cs_live_browser_hint',
    assign(value) { navigations.push(value); }};
  vm.runInNewContext(source, {frappe, document, location, URL, URLSearchParams,
    window: {frappe, addEventListener() {}}});
  return {calls, navigations, panel: elements.find(el => el.id === 'ss97-secure-ticket-payment')};
}

let result = page();
assert.match(result.panel.children[1].textContent, /Vous pouvez régler/);
assert.equal(result.calls.length, 1); // Browser paid/session/amount hints cannot confirm or charge.
result.panel.children[2].listeners.click();
assert.equal(result.calls[1].type, 'POST');
assert.deepEqual(JSON.parse(JSON.stringify(result.calls[1].args)), {issue: 'ISSUE-OWN'});
assert.deepEqual(result.navigations, ['https://checkout.stripe.com/c/pay/fixture']);

result = page({verified: true});
assert.equal(result.panel.children[1].textContent, 'Paiement confirmé.');
result.panel.children[2].listeners.click();
assert.equal(result.calls.length, 1);

for (const options of [{failure: true}, {verified: 'true'}]) {
  result = page(options);
  assert.equal(result.panel.children[2].disabled, true);
  assert.match(result.panel.children[1].textContent, /indisponible/);
}
for (const url of ['https://checkout.stripe.com.evil.example/','http://checkout.stripe.com/',
  'https://checkout.stripe.com:444/','https://secret@checkout.stripe.com/']) {
  result = page({url});
  result.panel.children[2].listeners.click();
  assert.deepEqual(result.navigations, []);
  assert.match(result.panel.children[1].textContent, /indisponible/);
}
result = page({user: 'Guest'});
assert.equal(result.panel, undefined);
assert.equal(result.calls.length, 0);
console.log('OK: browser hints, ownership arguments, POST, confirmed receipt, failure and URL guards.');
