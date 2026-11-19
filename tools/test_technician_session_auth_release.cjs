"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const script = fs.readFileSync(path.resolve(__dirname, "../softsystem97/public/js/technician_session_auth.js"), "utf8");

async function check(pathname, status, body, expectedRole) {
  const calls = [];
  let ready;
  const ctx = {
    location: {pathname},
    document: {readyState: "loading", addEventListener(event, handler) {
      if (event === "DOMContentLoaded") ready = handler;
    }},
    window: {ss97Auth: {STATE: "LOADING"}, dispatchEvent() {}},
    CustomEvent: function Event(name, options) { this.type = name; this.detail = options.detail; },
    fetch: (url, options) => {
      calls.push({url, options});
      return Promise.resolve({ok: status === 200, json: () => Promise.resolve({message: body})});
    }
  };
  vm.runInNewContext(script, ctx);
  if (!pathname.startsWith("/espace-technicien")) {
    assert.equal(ctx.window.ss97AuthResolve, undefined);
    return;
  }
  assert.equal(typeof ctx.window.ss97AuthResolve, "function");
  assert.equal(typeof ready, "function");
  ready();
  const a = new Promise(resolve => ctx.window.ss97AuthResolve(resolve));
  const b = new Promise(resolve => ctx.window.ss97AuthResolve(resolve));
  assert.equal((await a).isTechnician, expectedRole);
  assert.equal((await b).isTechnician, expectedRole);
  assert.equal(calls.length, 1, "concurrent checks are deduplicated");
  assert.equal(calls[0].url, "/api/method/softsystem97.portal.technician_access.my_technician_access");
  assert.equal(calls[0].options.credentials, "same-origin");
}

(async () => {
  await check("/espace-technicien/dashboard", 200, {authenticated: true, isTechnician: true}, true);
  await check("/espace-technicien/login", 200, {authenticated: true, isTechnician: false}, false);
  await check("/espace-technicien/dashboard", 503, {}, false);
  await check("/client/dashboard", 200, {authenticated: true, isTechnician: true});
  console.log("4 portal session adapter checks passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
