/* Push preferences for this GitHub Pages app.
   Requires a configured OneSignal *web* App ID (public ID, NOT REST API key).
   Safe to include on GitHub Pages: no notification SDK runs until configured. */
(function () {
  "use strict";
  var config = window.APP_PUSH_CONFIG;
  if (!config || !/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(config.oneSignalAppId || "")) return;
  if (!("serviceWorker" in navigator) || !("Notification" in window)) return;

  var types = ["projections", "results", "locked"];
  var storageKey = "push-preferences-" + config.appKey;
  var prefs = { enabled: false, projections: true, results: true, locked: true };
  try {
    var previous = JSON.parse(localStorage.getItem(storageKey) || "null");
    if (previous) {
      Object.keys(prefs).forEach(function (key) {
        if (typeof previous[key] === "boolean") prefs[key] = previous[key];
      });
    }
  } catch (e) { /* Storage may be disabled; use defaults. */ }

  var style = document.createElement("style");
  style.textContent = [
    "#app-push-root{position:fixed;right:14px;bottom:calc(16px + env(safe-area-inset-bottom));z-index:9000;font:14px/1.4 system-ui,-apple-system,sans-serif;color:#e9edf3}",
    "#app-push-root *{box-sizing:border-box}",
    "#app-push-toggle{display:block;margin-left:auto;border:1px solid #4a647a;border-radius:24px;padding:10px 16px;background:#142532;color:#fff;font:600 14px system-ui;box-shadow:0 4px 18px #0005;cursor:pointer}",
    "#app-push-panel{position:absolute;right:0;bottom:54px;width:min(310px,calc(100vw - 28px));padding:16px;background:#142532;border:1px solid #4a647a;border-radius:13px;box-shadow:0 12px 32px #0008}",
    "#app-push-panel[hidden]{display:none}",
    "#app-push-panel strong{display:block;font-size:16px;margin:0 0 5px}",
    "#app-push-panel p{margin:0 0 12px;color:#c2d0de;font-size:12px}",
    "#app-push-panel label{display:flex;align-items:center;gap:10px;padding:7px 0;color:#e9edf3}",
    "#app-push-panel input{width:16px;height:16px;accent-color:#5dd7a2}",
    "#app-push-action{background:#5dd7a2;color:#10251e;border:0;border-radius:9px;font:700 13px system-ui;padding:11px;width:100%;cursor:pointer;margin:10px 0 4px}",
    "#app-push-status{font-size:12px;color:#c2d0de;min-height:17px}",
    "@media(max-width:760px){#app-push-root{bottom:calc(86px + env(safe-area-inset-bottom))}}"
  ].join("\n");
  document.head.appendChild(style);

  var root = document.createElement("div");
  root.id = "app-push-root";
  root.innerHTML =
    '<button type="button" id="app-push-toggle" aria-expanded="false" aria-controls="app-push-panel">Alerts</button>' +
    '<div id="app-push-panel" hidden><strong>Notification settings</strong>' +
    '<p>Choose which updates you receive from this app. Notifications work on iPhone after adding it to your Home Screen.</p>' +
    '<label><input type="checkbox" data-push-type="projections"> Projections and new plays</label>' +
    '<label><input type="checkbox" data-push-type="results"> Graded results</label>' +
    '<label><input type="checkbox" data-push-type="locked"> Locked or official selections</label>' +
    '<button type="button" id="app-push-action">Enable notifications</button>' +
    '<div id="app-push-status" aria-live="polite">Connecting to push service…</div></div>';
  document.body.appendChild(root);
  var toggle = document.getElementById("app-push-toggle");
  var panel = document.getElementById("app-push-panel");
  var action = document.getElementById("app-push-action");
  var status = document.getElementById("app-push-status");
  var client = null;

  function save() {
    try { localStorage.setItem(storageKey, JSON.stringify(prefs)); } catch (e) {}
  }
  function syncTags() {
    if (!client) return;
    var tags = {};
    tags["push_" + config.appKey + "_enabled"] = prefs.enabled ? "1" : "0";
    types.forEach(function (type) {
      tags["push_" + config.appKey + "_" + type] = prefs[type] ? "1" : "0";
    });
    client.User.addTags(tags);
  }
  function update() {
    types.forEach(function (type) {
      var box = root.querySelector('[data-push-type="' + type + '"]');
      box.checked = prefs[type];
    });
    action.disabled = !client;
    action.textContent = prefs.enabled ? "Turn off alerts for this app" : "Enable notifications";
    if (client) {
      var subscribed = Boolean(client.User.PushSubscription.optedIn);
      status.textContent = prefs.enabled && subscribed ? "Alerts enabled" :
        prefs.enabled ? "Permission not active; enable again" :
        "Alerts for this app are off";
    }
  }
  toggle.addEventListener("click", function () {
    panel.hidden = !panel.hidden;
    toggle.setAttribute("aria-expanded", String(!panel.hidden));
  });
  root.querySelectorAll("[data-push-type]").forEach(function (box) {
    box.addEventListener("change", function () {
      prefs[box.getAttribute("data-push-type")] = box.checked;
      save();
      syncTags();
    });
  });
  action.addEventListener("click", async function () {
    if (!client) return;
    action.disabled = true;
    try {
      if (prefs.enabled) {
        // Do not optOut() here: other apps may share the same OneSignal origin.
        prefs.enabled = false;
      } else {
        // Must run from the tap handler to satisfy iOS permission requirements.
        await client.User.PushSubscription.optIn();
        if (!client.User.PushSubscription.optedIn) throw new Error("Permission was not granted. Check iPhone notification settings.");
        prefs.enabled = true;
      }
      save();
      syncTags();
    } catch (err) {
      status.textContent = err && err.message || "Unable to enable notifications.";
    } finally {
      update();
    }
  });
  update();
  window.OneSignalDeferred = window.OneSignalDeferred || [];
  window.OneSignalDeferred.push(async function (OneSignal) {
    try {
      var scope = new URL("./push/onesignal/", location.href).pathname;
      await OneSignal.init({
        appId: config.oneSignalAppId,
        safari_web_id: config.safariWebId,
        serviceWorkerPath: scope.replace(/^\//, "") + "OneSignalSDKWorker.js",
        serviceWorkerParam: { scope: scope },
        notifyButton: { enable: false },
        promptOptions: { slidedown: { prompts: [{ type: "push", autoPrompt: false }] } }
      });
      client = OneSignal;
      client.User.PushSubscription.addEventListener("change", update);
      // Synchronize tags only after this app has explicitly been enabled.
      if (prefs.enabled) syncTags();
      update();
    } catch (err) {
      status.textContent = "Push initialization failed: " + (err && err.message || err);
    }
  });
  var loader = document.createElement("script");
  loader.src = "https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.page.js";
  loader.defer = true;
  loader.onerror = function () { status.textContent = "Could not load the notification service."; };
  document.head.appendChild(loader);
})();
