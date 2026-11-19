/* Session-backed auth adapter for the existing SS97 website guards. */
(function () {
  'use strict';
  if (window.__ss97TechSessionAuth) return;
  if (!/^\/(?:espace-technicien|connexion-technicien)(?:\/|$)/.test(location.pathname)) return;
  window.__ss97TechSessionAuth = true;

  var METHOD = '/api/method/softsystem97.portal.technician_access.my_technician_access';
  var current = null;
  var pending = null;

  function installProfile(profile) {
    var auth = window.ss97Auth;
    if (auth) {
      auth.profile = profile;
      auth.STATE = profile.authenticated ? 'AUTHENTICATED' : 'UNAUTHENTICATED';
      auth.resolving = false;
    }
    try {
      window.dispatchEvent(new CustomEvent('ss97:auth', {
        detail: {state: profile.authenticated ? 'AUTHENTICATED' : 'UNAUTHENTICATED', profile: profile}
      }));
    } catch (e) {}
  }

  function resolve(cb) {
    cb = typeof cb === 'function' ? cb : function () {};
    if (current) { cb(current); return; }
    if (!pending) {
      pending = fetch(METHOD, {credentials: 'same-origin', headers: {'Accept': 'application/json'}})
        .then(function (r) { if (!r.ok) throw new Error('Authentication unavailable'); return r.json(); })
        .then(function (payload) {
          if (!payload || !payload.message || typeof payload.message.authenticated !== 'boolean') {
            throw new Error('Invalid authentication response');
          }
          current = payload.message;
          installProfile(current);
          return current;
        })
        .catch(function () {
          // A failed request is never a grant.  Do not trust a cached user ID.
          var failClosed = {authenticated: false, isTechnician: false, isAdmin: false, verificationError: true};
          installProfile(failClosed);
          pending = null;
          return failClosed;
        });
    }
    pending.then(cb);
  }

  // Replace the legacy resolver before its document-ready handlers run.
  // No profile is inferred from sessionStorage or permission-restricted list APIs.
  window.ss97AuthResolve = resolve;

  // If an earlier guard already displayed the refusal, make it re-evaluate.
  function refreshGuard() {
    if (typeof window.technician_route_guard === 'function') {
      window.technician_route_guard();
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', refreshGuard, {once: true});
  } else {
    refreshGuard();
  }
})();
