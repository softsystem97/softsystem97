/* Portal login and dashboard use the authenticated Frappe session, never arbitrary User-list queries. */
(function () {
  'use strict';
  if (window.__ss97TechSessionAuth) return;
  if (!/^\/(?:espace-technicien|connexion-technicien)(?:\/|$)/.test(location.pathname)) return;
  window.__ss97TechSessionAuth = true;

  var endpoint = '/api/method/softsystem97.portal.technician_access.my_technician_access';
  var inFlight = null;
  // Avoid treating a cached previous identity as authority; resolve per page load.
  function install(profile) {
    if (window.ss97Auth) {
      window.ss97Auth.profile = profile;
      window.ss97Auth.STATE = profile.authenticated ? 'AUTHENTICATED' : 'UNAUTHENTICATED';
      window.ss97Auth.resolving = false;
    }
    try {
      window.dispatchEvent(new CustomEvent('ss97:auth', {
        detail: {
          state: profile.authenticated ? 'AUTHENTICATED' : 'UNAUTHENTICATED',
          profile: profile
        }
      }));
    } catch (ignored) { /* Older browsers still get the callback. */ }
  }

  function resolve(callback) {
    callback = typeof callback === 'function' ? callback : function () {};
    if (!inFlight) {
      inFlight = fetch(endpoint, {credentials: 'same-origin', headers: {'Accept': 'application/json'}})
        .then(function (response) {
          if (!response.ok) throw Error('Technician session unavailable');
          return response.json();
        })
        .then(function (payload) {
          if (!payload || !payload.message ||
              typeof payload.message.authenticated !== 'boolean' ||
              typeof payload.message.isTechnician !== 'boolean') {
            throw Error('Unexpected technician status');
          }
          install(payload.message);
          return payload.message;
        })
        .catch(function () {
          // Unavailable services must never grant technician access.
          var denied = {authenticated: false, isTechnician: false, isAdmin: false, verificationError: true};
          install(denied);
          return denied;
        })
        .finally(function () { inFlight = null; });
    }
    inFlight.then(callback);
  }

  window.ss97AuthResolve = resolve;
  function recheck() {
    if (typeof window.technician_route_guard === 'function') window.technician_route_guard();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', recheck, {once: true});
  } else {
    recheck();
  }
})();
