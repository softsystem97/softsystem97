/* Portal login and dashboard use the authenticated Frappe session, never arbitrary User-list queries. */
(function () {
  'use strict';
  if (window.__ss97TechSessionAuth) return;
  if (!/^\/(?:espace-technicien|connexion-technicien)(?:\/|$)/.test(location.pathname)) return;
  window.__ss97TechSessionAuth = true;

  var endpoint = '/api/method/softsystem97.portal.technician_access.my_technician_access';
  var inFlight = null;
  var verifiedProfile = null;
  var emittingVerifiedState = false;
  function recheck() {
    if (typeof window.technician_route_guard === 'function') window.technician_route_guard();
  }

  // Avoid treating a cached previous identity as authority; resolve per page load.
  function install(profile) {
    verifiedProfile = profile;
    if (window.ss97Auth) {
      window.ss97Auth.profile = profile;
      window.ss97Auth.STATE = profile.authenticated ? 'AUTHENTICATED' : 'UNAUTHENTICATED';
      window.ss97Auth.resolving = false;
    }
    emittingVerifiedState = true;
    try {
      window.dispatchEvent(new CustomEvent('ss97:auth', {
        detail: {
          state: profile.authenticated ? 'AUTHENTICATED' : 'UNAUTHENTICATED',
          profile: profile
        }
      }));
    } catch (ignored) { /* Older browsers still get the callback. */ }
    finally { emittingVerifiedState = false; }
    // The dashboard's legacy guard may already be in ERROR by the time the
    // server replies. Re-run it with the verified session instead of leaving
    // the stale 'no technician access' wall on screen.
    recheck();
  }

  // The historical ss97_auth_portal_v13.js performs client-side get_list
  // requests for Technician Application and Employee. Website Users often do
  // not have read permission for those DocTypes, so it can overwrite an
  // already-verified role with a false denial while loading. Accept only the
  // current user returned by our server endpoint as authority.
  if (typeof window.addEventListener === 'function') {
    window.addEventListener('ss97:auth', function (event) {
      if (emittingVerifiedState || !verifiedProfile ||
          !verifiedProfile.authenticated || !verifiedProfile.user) return;
      var legacy = event && event.detail && event.detail.profile;
      if (!legacy || !legacy.authenticated ||
          String(legacy.user || '').toLowerCase() !==
            String(verifiedProfile.user).toLowerCase()) return;
      if (legacy.isTechnician !== verifiedProfile.isTechnician ||
          legacy.isAdmin !== verifiedProfile.isAdmin) {
        install(verifiedProfile);
      }
    });
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
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', recheck, {once: true});
  } else {
    recheck();
  }
})();
