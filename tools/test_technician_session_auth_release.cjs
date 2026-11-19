"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const script = fs.readFileSync(path.resolve(__dirname, "../softsystem97/public/js/technician_session_auth.js"), "utf8");

async function check(pathname, status, body, expectedRole) {
  const calls = [];
  const redirects = [];
  let ready;
  const ctx = {
    location: {pathname, replace(url) { redirects.push(url); }},
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
  if (pathname === "/espace-technicien/login") {
    assert.deepEqual(redirects, expectedRole ? ["/espace-technicien/dashboard"] : []);
  }
}

(async () => {
  await check("/espace-technicien/dashboard", 200, {authenticated: true, isTechnician: true}, true);
  await check("/espace-technicien/login", 200, {authenticated: true, isTechnician: false}, false);
  await check("/espace-technicien/login", 200, {authenticated: true, isTechnician: true}, true);
  await check("/espace-technicien/dashboard", 503, {}, false);
  await check("/client/dashboard", 200, {authenticated: true, isTechnician: true});
  await checkLegacyDenialIsRepaired();
  await checkLegacyGrantAfterServerFailureIsRejected();
  await checkDashboardReadyOnlyAfterVerifiedRole();
  await checkDashboardDeniedWhenServerUnavailable();
  await checkProtectedChildPageRecoversFromLateDenial();
  await checkProtectedChildPageStaysClosedWithoutVerifiedRole();
  console.log("11 portal session adapter checks passed");
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

async function checkDashboardReadyOnlyAfterVerifiedRole() {
  const events = [];
  const attrs = {'data-ss97-tech-state': 'ERROR'};
  let onChange;
  const body = {
    getAttribute(name) { return attrs[name]; },
    setAttribute(name, value) {
      attrs[name] = value;
      if (onChange) onChange();
    }
  };
  const ctx = {
    location: {pathname: '/espace-technicien/dashboard'},
    document: {readyState: 'complete', body},
    window: {dispatchEvent(event) { events.push(event.type); }},
    MutationObserver: class {
      constructor(callback) { onChange = callback; }
      observe(target, options) {
        assert.equal(target, body);
        assert.equal(options.attributeFilter[0], 'data-ss97-tech-state');
      }
    },
    CustomEvent: function Event(name) { this.type = name; },
    fetch: () => Promise.resolve({ok: true, json: () => Promise.resolve({message: {
      authenticated: true, isTechnician: true, user: 'n2@example.invalid'
    }})})
  };
  vm.runInNewContext(script, ctx);
  await new Promise(done => ctx.window.ss97AuthResolve(done));
  assert.equal(attrs['data-ss97-tech-state'], 'READY');
  assert.ok(events.includes('ss97:tech-ready'), 'dashboard boot is awakened');
  body.setAttribute('data-ss97-tech-state', 'ERROR');
  assert.equal(attrs['data-ss97-tech-state'], 'READY', 'late legacy denial is repaired');
}

async function checkDashboardDeniedWhenServerUnavailable() {
  const attrs = {'data-ss97-tech-state': 'ERROR'};
  const ctx = {
    location: {pathname: '/espace-technicien/dashboard'},
    document: {readyState: 'complete', body: {
      getAttribute(name) { return attrs[name]; },
      setAttribute(name, value) { attrs[name] = value; }
    }},
    window: {dispatchEvent() {}},
    CustomEvent: function Event(name) { this.type = name; },
    fetch: () => Promise.resolve({ok: false})
  };
  vm.runInNewContext(script, ctx);
  await new Promise(done => ctx.window.ss97AuthResolve(done));
  assert.equal(attrs['data-ss97-tech-state'], 'ERROR', 'server outage must not grant access');
}

async function checkProtectedChildPageRecoversFromLateDenial() {
  for (const route of ['profil', 'agenda', 'rapports', 'messages']) {
    const listeners = {};
    const events = [];
    const attributes = {'data-ss97-tech-state': 'ERROR'};
    const login = {style: {display: 'block'}};
    const privatePanel = {style: {display: 'none'}};
    let observeChange;
    const body = {
      getAttribute(key) { return attributes[key]; },
      setAttribute(key, value) { attributes[key] = value; }
    };
    const ctx = {
      location: {pathname: '/espace-technicien/' + route},
      document: {
        readyState: 'complete', body,
        querySelectorAll(selector) {
          if (selector === '[data-tech-login-required]') return [login];
          if (selector === '[data-tech-private]') return [privatePanel];
          return [];
        }
      },
      window: {
        ss97Auth: {profile: null, STATE: 'LOADING'},
        addEventListener(name, handler) { (listeners[name] ??= []).push(handler); },
        dispatchEvent(event) {
          events.push(event.type);
          (listeners[event.type] || []).forEach(handler => handler(event));
        }
      },
      CustomEvent: function Event(name, options) { this.type = name; this.detail = options?.detail; },
      MutationObserver: class {
        constructor(callback) { observeChange = callback; }
        observe(target, options) {
          assert.equal(target, body);
          assert.equal(options.subtree, true);
        }
      },
      fetch: () => Promise.resolve({ok: true, json: () => Promise.resolve({message: {
        authenticated: true, isTechnician: true, isAdmin: false, user: 'n2@example.invalid'
      }})})
    };
    vm.runInNewContext(script, ctx);
    await new Promise(done => ctx.window.ss97AuthResolve(done));
    assert.equal(attributes['data-ss97-tech-state'], 'READY', route);
    assert.equal(login.style.display, 'none', route + ' must hide false denial');
    assert.equal(privatePanel.style.display, '', route + ' must show its private content');
    assert.ok(events.includes('ss97:tech-ready'), route + ' must start its page-specific loader');
    // A delayed legacy check can still re-hide the page. Restore only after
    // having already verified the user's role with the authenticated API.
    login.style.display = 'block';
    privatePanel.style.display = 'none';
    attributes['data-ss97-tech-state'] = 'ERROR';
    observeChange();
    assert.equal(login.style.display, 'none', route);
    assert.equal(privatePanel.style.display, '', route);
    assert.equal(attributes['data-ss97-tech-state'], 'READY', route);
  }
}

async function checkProtectedChildPageStaysClosedWithoutVerifiedRole() {
  const attributes = {'data-ss97-tech-state': 'ERROR'};
  const login = {style: {display: 'block'}};
  const privatePanel = {style: {display: 'none'}};
  const ctx = {
    location: {pathname: '/espace-technicien/rapports'},
    document: {
      readyState: 'complete',
      body: {
        getAttribute(key) { return attributes[key]; },
        setAttribute(key, value) { attributes[key] = value; }
      },
      querySelectorAll(selector) {
        return selector === '[data-tech-private]' ? [privatePanel] : [login];
      }
    },
    window: {dispatchEvent() {}},
    CustomEvent: function Event(name) { this.type = name; },
    fetch: () => Promise.resolve({ok: true, json: () => Promise.resolve({message: {
      authenticated: true, isTechnician: false, user: 'customer@example.invalid'
    }})})
  };
  vm.runInNewContext(script, ctx);
  await new Promise(done => ctx.window.ss97AuthResolve(done));
  assert.equal(attributes['data-ss97-tech-state'], 'ERROR');
  assert.equal(privatePanel.style.display, 'none');
  assert.notEqual(login.style.display, 'none');
}
