'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.resolve(__dirname, '../softsystem97/public/js/technician_session_auth.js'), 'utf8');

async function check(status, body, expected) {
  let requested = [];
  let handler;
  const ctx = {
    location: {pathname: '/espace-technicien/dashboard'},
    document: {readyState: 'loading', addEventListener(event, fn) { if (event === 'DOMContentLoaded') handler = fn; }},
    window: {ss97Auth: {STATE: 'LOADING'}, dispatchEvent() {}},
    CustomEvent: function CustomEvent(name, payload) { this.type = name; this.detail = payload.detail; },
    fetch: (url, options) => {
      requested.push({url, options});
      return Promise.resolve({ok: status === 200, json: () => Promise.resolve({message: body})});
    }
  };
  vm.runInNewContext(source, ctx);
  assert.equal(typeof ctx.window.ss97AuthResolve, 'function');
  const first = new Promise(resolve => ctx.window.ss97AuthResolve(resolve));
  const second = new Promise(resolve => ctx.window.ss97AuthResolve(resolve));
  assert.equal(typeof handler, 'function');
  handler();
  const result = await first;
  assert.deepEqual(result.isTechnician, expected);
  assert.equal((await second).isTechnician, expected);
  assert.equal(requested.length, 1, 'deduplicate simultaneous checks');
  assert.equal(requested[0].options.credentials, 'same-origin');
  assert.equal(requested[0].url, '/api/method/softsystem97.portal.technician_access.my_technician_access');
  assert.equal(ctx.window.ss97Auth.STATE, result.authenticated ? 'AUTHENTICATED' : 'UNAUTHENTICATED');
}

(async () => {
  await check(200, {authenticated: true, isTechnician: true, isAdmin: false}, true);
  await check(200, {authenticated: true, isTechnician: false, isAdmin: false}, false);
  await check(503, {}, false);
  console.log('3 session-backed frontend checks passed');
})().catch(e => {console.error(e); process.exitCode = 1;});
