/* Portal login and dashboard use the authenticated Frappe session, never arbitrary User-list queries. */
(function () {
  'use strict';
  if (window.__ss97TechSessionAuth) return;
  if (!/^\/(?:espace-technicien|connexion-technicien)(?:\/|$)/.test(location.pathname)) return;
  window.__ss97TechSessionAuth = true;
  try { console.info('[SS97] SESSION_GATE_BRIDGE_V4'); } catch (ignored) {}

  var endpoint = '/api/method/softsystem97.portal.technician_access.my_technician_access';
  var inFlight = null;
  var verifiedProfile = null;
  var emittingVerifiedState = false;
  var dashboardObserver = null;
  function recheck() {
    if (typeof window.technician_route_guard === 'function') window.technician_route_guard();
  }

  function reconcileDashboard() {
    // The historical dashboard sets a second, independent READY/ERROR flag.
    // Its client-side get_list checks can fail on Website Users even after the
    // server has verified their technician role. Only a positive response from
    // the authenticated Frappe endpoint may restore the private dashboard.
    if (!/^\/espace-technicien\/(?:dashboard|tableau-de-bord)\/?$/.test(location.pathname)) return;
    if (!verifiedProfile || verifiedProfile.verificationError ||
        !verifiedProfile.authenticated || !verifiedProfile.isTechnician) return;
    var body = document.body;
    if (!body) return;
    if (body.getAttribute('data-ss97-tech-state') !== 'READY') {
      body.setAttribute('data-ss97-tech-state', 'READY');
      try { window.dispatchEvent(new CustomEvent('ss97:tech-ready')); }
      catch (ignored) { /* The attribute is sufficient for older pages. */ }
    }
    if (!dashboardObserver && typeof MutationObserver === 'function') {
      dashboardObserver = new MutationObserver(reconcileDashboard);
      dashboardObserver.observe(body, {
        attributes: true, attributeFilter: ['data-ss97-tech-state']
      });
    }
  }

  // Avoid treating a cached previous identity as authority; resolve per page load.
  function install(profile) {
    verifiedProfile = profile;
    try {
      console.info('[SS97] SESSION_GATE_VERIFIED',
        profile.verificationError ? 'unavailable' :
        (profile.authenticated && profile.isTechnician ? 'allowed' : 'denied'));
    } catch (ignored) {}
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
    reconcileDashboard();
  }

  // The historical ss97_auth_portal_v13.js performs client-side get_list
  // requests for Technician Application and Employee. Website Users often do
  // not have read permission for those DocTypes, so it can overwrite an
  // already-verified role with a false denial while loading. Accept only the
  // current user returned by our server endpoint as authority.
  if (typeof window.addEventListener === 'function') {
    window.addEventListener('ss97:auth', function (event) {
      if (emittingVerifiedState || !verifiedProfile) return;
      var legacy = event && event.detail && event.detail.profile;
      if (!legacy || !legacy.authenticated) return;
      if (!verifiedProfile.authenticated) {
        // A legacy file must not turn a failed or unavailable server check
        // into access. A subsequent login rechecks the server normally.
        install(verifiedProfile);
        return;
      }
      if (!verifiedProfile.user ||
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
  function boot() {
    recheck();
    // The historical login page may finish its own incorrect get_list check
    // before this script loads and never call ss97AuthResolve again. Initiate
    // the server check here, even when no dashboard guard is present.
    resolve(function (profile) {
      if (/^\/espace-technicien\/login\/?$/.test(location.pathname) &&
          profile.authenticated && profile.isTechnician) {
        // A fixed same-origin destination avoids trusting a stale client
        // profile or a user-controlled redirect-to query string.
        location.replace('/espace-technicien/dashboard');
      }
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, {once: true});
  } else {
    boot();
  }
})();
