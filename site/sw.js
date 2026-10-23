/* sw.js - optional offline cache. Network first, falls back to what was cached, so the site (and every gallery file
   you have already looked at) keeps working when the connection does not. Only same-origin GETs are stored. */
const CACHE = "jpeg-unplugged-v6";
// Optional data, evidence and gallery code/assets enter the cache only when viewed.
const SHELL = ["./", "index.html", "css/style.css", "js/core.js", "js/hero.js", "js/census.js", "js/extra.js", "js/main.js", "js/findings.js", "js/gallery.js",
  "js/top100.js", "data/top100.json", "fonts/archivo-var-latin.woff2", "fonts/silkscreen-regular.ttf"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()).catch(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const r = e.request;
  if (r.method !== "GET" || new URL(r.url).origin !== self.location.origin) return;
  e.respondWith(
    fetch(r).then((res) => {
      if (res && res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(r, copy)); }
      return res;
    }).catch(() => caches.match(r).then((m) => m || caches.match("index.html")))
  );
});
