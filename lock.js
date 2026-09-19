// =============================================================
// Passcode/login lock screen. Drop this on any page with:
//     <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
//     <script src="lock.js"></script>
// (must load AFTER the supabase-js CDN script, and NOT deferred,
// so it can hide the page before anything paints).
//
// Uses real Supabase Auth (email + password) instead of a hardcoded
// passcode, so the same login gates both the dashboard UI and the
// underlying data (once app_state's RLS policies are restricted to
// the "authenticated" role - see README).
//
// Skips itself entirely inside an iframe (e.g. po-water.html embedded
// in health.html) - the parent page already gates access, and since
// iframe + parent share localStorage on the same origin, the
// Supabase session the parent logged in with is already visible here.
// =============================================================
(function () {
  'use strict';

  var SUPABASE_URL = 'https://qigzwmiypboijszfrhkm.supabase.co';
  var SUPABASE_KEY = 'sb_publishable_EAe3cddNpZ8vdw17a8kl0w_zDu9CfDb';

  function isEmbedded() {
    try { return window.self !== window.top; } catch (e) { return true; }
  }
  if (isEmbedded()) return;

  // Hide the page immediately, synchronously, before first paint.
  document.documentElement.style.visibility = 'hidden';

  function reveal() {
    document.documentElement.style.visibility = '';
    var el = document.getElementById('lockScreen');
    if (el) el.remove();
  }

  function showLoginScreen(supa) {
    function mount() {
      var wrap = document.createElement('div');
      wrap.id = 'lockScreen';
      wrap.innerHTML =
        '<style>' +
        '#lockScreen{position:fixed;inset:0;z-index:99999;background:#050506;' +
        'display:flex;align-items:center;justify-content:center;padding:20px;' +
        'font-family:-apple-system,BlinkMacSystemFont,"Inter","Segoe UI",Roboto,sans-serif;}' +
        '#lockScreen .lock-card{width:100%;max-width:320px;background:rgba(255,255,255,0.04);' +
        'border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:28px;' +
        'backdrop-filter:blur(24px) saturate(1.2);-webkit-backdrop-filter:blur(24px) saturate(1.2);' +
        'box-shadow:0 12px 40px rgba(0,0,0,0.45);text-align:center;}' +
        '#lockScreen h1{margin:0 0 18px;font-size:20px;font-weight:700;' +
        'background:linear-gradient(180deg,#FFFFFF 0%,#C7C4BC 120%);-webkit-background-clip:text;' +
        'background-clip:text;-webkit-text-fill-color:transparent;color:transparent;}' +
        '#lockScreen input{width:100%;box-sizing:border-box;margin-bottom:10px;padding:11px 14px;' +
        'border:1px solid rgba(255,255,255,0.08);border-radius:12px;background:rgba(0,0,0,0.28);' +
        'color:#FAFAFA;font-family:inherit;font-size:14px;outline:none;}' +
        '#lockScreen input:focus{border-color:rgba(255,255,255,0.28);}' +
        '#lockScreen button{width:100%;padding:11px;border:0;border-radius:12px;' +
        'background:linear-gradient(180deg,#FFFFFF 0%,#E8E5DD 100%);color:#0A0A0B;' +
        'font-family:inherit;font-weight:700;font-size:13px;cursor:pointer;}' +
        '#lockScreen button:disabled{opacity:0.6;cursor:default;}' +
        '#lockScreen .lock-err{color:#FF6B6B;font-size:12px;margin-top:10px;min-height:14px;}' +
        '</style>' +
        '<div class="lock-card">' +
          '<h1>Dashboard</h1>' +
          '<input id="lockEmail" type="email" placeholder="Email" autocomplete="username">' +
          '<input id="lockPass" type="password" placeholder="Password" autocomplete="current-password">' +
          '<button id="lockBtn" type="button">Log in</button>' +
          '<div class="lock-err" id="lockErr"></div>' +
        '</div>';
      document.body.appendChild(wrap);
      document.documentElement.style.visibility = '';

      var btn = document.getElementById('lockBtn');
      var errEl = document.getElementById('lockErr');
      var emailEl = document.getElementById('lockEmail');
      var passEl = document.getElementById('lockPass');

      function attempt() {
        var email = emailEl.value.trim();
        var password = passEl.value;
        if (!email || !password) return;
        errEl.textContent = '';
        btn.disabled = true;
        btn.textContent = 'Logging in…';
        supa.auth.signInWithPassword({ email: email, password: password }).then(function (res) {
          if (res.error) {
            btn.disabled = false;
            btn.textContent = 'Log in';
            errEl.textContent = 'Wrong email or password.';
            return;
          }
          // Full reload (not just reveal()) so every other script on the
          // page - sync.js, topbar.js, gym.html's own sync - creates its
          // Supabase client AFTER the session is already in localStorage,
          // instead of possibly having already made an unauthenticated
          // call before this login resolved.
          window.location.reload();
        }).catch(function () {
          btn.disabled = false;
          btn.textContent = 'Log in';
          errEl.textContent = "Couldn't reach the login service.";
        });
      }
      btn.addEventListener('click', attempt);
      passEl.addEventListener('keydown', function (e) { if (e.key === 'Enter') attempt(); });
      emailEl.addEventListener('keydown', function (e) { if (e.key === 'Enter') passEl.focus(); });
    }
    if (document.body) mount();
    else document.addEventListener('DOMContentLoaded', mount, { once: true });
  }

  function boot() {
    if (!window.supabase) {
      // supabase-js failed to load - fail open rather than permanently
      // hiding the page behind a lock screen that can never resolve.
      document.documentElement.style.visibility = '';
      return;
    }
    var supa = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY);
    supa.auth.getSession().then(function (res) {
      if (res.data && res.data.session) { reveal(); return; }
      showLoginScreen(supa);
    }).catch(function () {
      document.documentElement.style.visibility = '';
    });
  }

  boot();
})();
