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
  await checkLegacyDenialIsRepaired();
  await checkLegacyGrantAfterServerFailureIsRejected();
  console.log("6 portal session adapter checks passed");
})().catch(error => { console.error(error); process.exitCode = 1; });

async function checkLegacyDenialIsRepaired() {
  const listeners = {};
  const calls = [];
  const legacy = {authenticated: true, isTechnician: false, isAdmin: false, user: "n2@example.invalid"};
  const ctx = {
    location: {pathname: "/espace-technicien/dashboard"},
    document: {readyState: "complete"},
    window: {
      ss97Auth: {profile: legacy, STATE: "AUTHENTICATED"},
      addEventListener(name, handler) { (listeners[name] ??= []).push(handler); },
      dispatchEvent(event) { (listeners[event.type] || []).forEach(handler => handler(event)); },
      technician_route_guard() { calls.push("guard"); }
    },
    CustomEvent: function Event(name, options) { this.type = name; this.detail = options.detail; },
    fetch: () => Promise.resolve({ok: true, json: () => Promise.resolve({message: {
      authenticated: true, isTechnician: true, isAdmin: false, user: "n2@example.invalid"
    }})})
  };
  vm.runInNewContext(script, ctx);
  const verified = await new Promise(done => ctx.window.ss97AuthResolve(done));
  assert.equal(verified.isTechnician, true);
  assert.equal(ctx.window.ss97Auth.profile.isTechnician, true);
  assert.ok(calls.includes("guard"), "guard must be retried after the authoritative reply");
  ctx.window.ss97Auth.profile = legacy;
  ctx.window.dispatchEvent(new ctx.CustomEvent("ss97:auth", {detail: {
    state: "AUTHENTICATED", profile: legacy
  }}));
  assert.equal(ctx.window.ss97Auth.profile.isTechnician, true,
    "a late client-side get_list denial must not overwrite the server result");
  assert.ok(calls.length >= 3, "the blocked dashboard is rechecked after the stale event");
  assert.equal(verified.user, "n2@example.invalid");
}

async function checkLegacyGrantAfterServerFailureIsRejected() {
  const listeners = {};
  const legacy = {authenticated: true, isTechnician: true, user: "someone@example.invalid"};
  const ctx = {
    location: {pathname: "/espace-technicien/dashboard"},
    document: {readyState: "complete"},
    window: {
      ss97Auth: {STATE: "LOADING", profile: null},
      addEventListener(name, handler) { (listeners[name] ??= []).push(handler); },
      dispatchEvent(event) { (listeners[event.type] || []).forEach(handler => handler(event)); }
    },
    CustomEvent: function Event(name, options) { this.type = name; this.detail = options.detail; },
    fetch: () => Promise.resolve({ok: false})
  };
  vm.runInNewContext(script, ctx);
  const result = await new Promise(done => ctx.window.ss97AuthResolve(done));
  assert.equal(result.isTechnician, false);
  ctx.window.ss97Auth.profile = legacy;
  ctx.window.dispatchEvent(new ctx.CustomEvent("ss97:auth", {detail: {
    state: "AUTHENTICATED", profile: legacy
  }}));
  assert.equal(ctx.window.ss97Auth.profile.isTechnician, false,
    "legacy code cannot grant access after a failed server check");
}
