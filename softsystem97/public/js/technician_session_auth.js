/* Every technician portal page uses the current Frappe session, not User-list queries. */
(function () {
  'use strict';
  if (window.__ss97TechSessionAuth) return;
  if (!/^\/(?:espace-technicien|connexion-technicien)(?:\/|$)/.test(location.pathname)) return;
  window.__ss97TechSessionAuth = true;
  try { console.info('[SS97] SESSION_GATE_BRIDGE_V5'); } catch (ignored) {}

  var endpoint = '/api/method/softsystem97.portal.technician_access.my_technician_access';
  var inFlight = null;
  var verifiedProfile = null;
  var emittingVerifiedState = false;
  var protectedObserver = null;
  function recheck() {
    if (typeof window.technician_route_guard === 'function') window.technician_route_guard();
  }

  function reconcileProtectedPage() {
    // Older Web Page records (agenda, profile, reports, messages, dashboard)
    // independently overwrite the auth panel after loading. Their get_list
    // requests can fail for a valid Website User. Restore only the generic
    // technician shell; each business API still checks ticket permissions.
    if (!/^\/espace-technicien\/(?!login(?:\/|$))/.test(location.pathname)) return;
    if (!verifiedProfile) return;
    var body = document.body;
    if (!body) return;
    var authorized = !verifiedProfile.verificationError &&
      verifiedProfile.authenticated && verifiedProfile.isTechnician;
    var state = authorized ? 'READY' : 'ERROR';
    var changed = false;
    if (body.getAttribute('data-ss97-tech-state') !== state) {
      body.setAttribute('data-ss97-tech-state', state);
      changed = true;
    }
    if (typeof document.querySelectorAll === 'function') {
      Array.prototype.forEach.call(document.querySelectorAll('[data-tech-login-required]'), function (panel) {
        var desired = authorized ? 'none' : '';
        if (panel.style && panel.style.display !== desired) {
          panel.style.display = desired;
          changed = true;
        }
      });
      Array.prototype.forEach.call(document.querySelectorAll('[data-tech-private]'), function (panel) {
        var desired = authorized ? '' : 'none';
        if (panel.style && panel.style.display !== desired) {
          panel.style.display = desired;
          changed = true;
        }
      });
    }
    if (authorized && changed) {
      try { window.dispatchEvent(new CustomEvent('ss97:tech-ready')); }
      catch (ignored) { /* Legacy pages can also check the body attribute. */ }
    }
    if (!protectedObserver && typeof MutationObserver === 'function') {
      protectedObserver = new MutationObserver(reconcileProtectedPage);
      protectedObserver.observe(body, {
        attributes: true,
        attributeFilter: ['data-ss97-tech-state', 'style'],
        subtree: true
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
    // The legacy guard may already be in ERROR on any protected page.
    recheck();
    reconcileProtectedPage();
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
      if (!legacy) return;
      if (!verifiedProfile.authenticated) {
        // A legacy file must not turn a failed or unavailable server check
        // into access. A subsequent login rechecks the server normally.
        install(verifiedProfile);
        return;
      }
      if (legacy.authenticated !== verifiedProfile.authenticated ||
          legacy.isTechnician !== verifiedProfile.isTechnician ||
          legacy.isAdmin !== verifiedProfile.isAdmin ||
          String(legacy.user || '').toLowerCase() !==
            String(verifiedProfile.user || '').toLowerCase()) {
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
