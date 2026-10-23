/* main.js - boot order: read the URL, load the data, build everything, wire the real network. */
(function () {
  "use strict";
  var JU = window.JU;

  function boot() {
    var q = new URLSearchParams(location.search).get("power");
    var wantOff = q === "off" || q === "archive" || location.hash === "#unplugged";
    if (!wantOff && navigator.onLine === false) {
      wantOff = true;
      JU.toast("Your browser reports no connection, so the page started unplugged. Previously viewed content may still be available.", 7000);
    }
    JU.load().then(function () {
      var sample = JU.isSample();
      document.body.classList.toggle("is-sample", sample);
      JU.$("#sample-banner").hidden = !sample;
      JU.bindAll();
      JU.initHero();
      JU.initTop100();
      JU.initFindings();
      JU.initCensus();
      if (JU.initExtra) JU.initExtra();
      JU.setPower(wantOff ? "off" : "on", q === "archive", { force: true, boot: true });
      loadGallery();
      dataCheck();
      registerWorker();
    });

    /* the visitor's real connection: if it drops, the page follows */
    window.addEventListener("offline", function () {
      if (JU.state.power === "on") { JU.setPower("off", false, { auto: true }); }
      JU.toast("Your connection just dropped. The page switched to unplugged; content already loaded remains available.", 8000);
    });
    window.addEventListener("online", function () { JU.toast("Back online. The plug is yours to put back in.", 4000); });
  }

  function loadGallery() {
    var started = false;
    function start() {
      if (started) return; started = true;
      var script = document.createElement("script"); script.src = "js/gallery.js";
      var loaded = new Promise(function (resolve, reject) {
        script.onload = resolve; script.onerror = function () { reject(new Error("Could not load the gallery code.")); };
      });
      document.head.appendChild(script);
      Promise.all([loaded, JU.loadGallery()]).then(function () { JU.bindAll(); JU.initGallery(); JU.initFindings(); }).catch(function (e) {
        var err = JU.$("#gallery-error"); err.hidden = false; err.textContent = e.message;
      });
    }
    start();
  }

  function dataCheck() {
    var el = JU.$("#datacheck"); if (!el) return;
    var d = JU.data, parts = [];
    if (d.errors.census || d.errors.collections) { el.textContent = "Data check: could not load " + ["census", "collections"].filter(function (k) { return d.errors[k]; }).join(" and ") + ".json."; el.classList.add("bad"); return; }
    var miss = JU.missingKeys(d.census), mism = JU.crossCheck(d.census, d.collections);
    if (miss.length) parts.push("census.json is missing: " + miss.join(", "));
    if (mism.length) parts.push(mism.length + " mismatch(es) between census.json and collections.json: " + mism.slice(0, 4).join("; "));
    el.textContent = parts.length ? "Data check FAILED. " + parts.join(". ") : "Data check: census.json agrees with a recount of collections.json (" + JU.fmt(d.collections.collections.length) + " rows)." + (JU.isSample() ? " Both files are marked sample." : "");
    el.classList.toggle("bad", parts.length > 0);
    if (parts.length) console.warn("[jpeg-unplugged] " + parts.join(" | "));
  }

  function registerWorker() {
    if (!("serviceWorker" in navigator)) return;
    if (!(location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) return;
    if (new URLSearchParams(location.search).has("nosw")) return;
    navigator.serviceWorker.register("sw.js").catch(function () { /* optional */ });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
