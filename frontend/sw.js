/* Service worker: keep the app usable when the network is not.
 *
 * Why this exists
 * ---------------
 * A triage app that dies without signal fails at exactly the moment it is most
 * needed. Someone standing in a dead spot worrying about chest pain should
 * still be able to open this, read the emergency numbers, look up what a
 * symptom means, and find which hospital to go to.
 *
 * The design rule everywhere below: cached information is fine, cached
 * *judgement* is not.
 *
 * What is cached, and what is deliberately not
 * --------------------------------------------
 * Cached — the shell, the symptom vocabulary, the specialities and the doctor
 * directory. All of it is reference material that changes on deploy, not per
 * request, and is just as true offline as online.
 *
 * Never cached — /triage. It is a POST, so it is not cacheable anyway, but the
 * more important reason is that it must never appear to work offline. Replaying
 * a previous answer for a new set of symptoms would be the single most
 * dangerous thing this file could do: the user would read a stale grade as a
 * verdict on what they just typed. Offline triage fails loudly instead, and the
 * app tells them to call 112 if it is urgent.
 *
 * The emergency number needs none of this. tel: links are handled by the dialer
 * and work with no network, no cache and no service worker — which is why the
 * 112 button was built as a plain link rather than anything scripted.
 */

/* Bump to invalidate every cache. Old caches are deleted on activate, so a
 * stale shell cannot survive a deploy — a real hazard when the thing being
 * updated is medical guidance. */
const CACHE_VERSION = "triage-v1";
const SHELL_CACHE = `${CACHE_VERSION}-shell`;
const DATA_CACHE = `${CACHE_VERSION}-data`;

/* Everything needed to render the app with no network at all. */
const SHELL_ASSETS = [
  "./",
  "./index.html",
  "./styles.css",
  "./app.js",
  "./manifest.json",
];

/* Reference endpoints worth keeping. Each is read-only, changes only on
 * deploy, and is useful offline. */
const CACHEABLE_API = ["/symptoms", "/specialties", "/doctors", "/languages"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      /* addAll is atomic: one failed asset aborts the install and the old
       * worker stays active, rather than leaving a half-cached shell that
       * breaks in ways nobody can reproduce. */
      .then((cache) => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((name) => !name.startsWith(CACHE_VERSION))
            .map((name) => caches.delete(name))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;

  /* Anything that is not a plain GET goes straight to the network. That is
   * every POST /triage: no cache, no fallback, no stale answer. */
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  /* Navigations fall back to the cached shell so the app opens offline
   * instead of showing the browser's dinosaur. */
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("./index.html"))
    );
    return;
  }

  const isApi = CACHEABLE_API.some((path) => url.pathname.startsWith(path));

  if (isApi) {
    event.respondWith(staleWhileRevalidate(request, DATA_CACHE));
    return;
  }

  /* Same-origin static assets: cache first, since they only change when
   * CACHE_VERSION does. */
  if (url.origin === self.location.origin) {
    event.respondWith(cacheFirst(request, SHELL_CACHE));
  }
});

/* Serve the cached copy immediately, refresh it in the background. The user
 * gets an instant answer and the next load gets the newer data. */
async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  const network = fetch(request)
    .then((response) => {
      if (response && response.ok) cache.put(request, response.clone());
      return response;
    })
    .catch(() => null);

  const response = cached || (await network);
  if (response) return response;

  /* Never seen online, and offline now. A JSON error is returned rather than
   * an exception so the app can show its own offline message instead of an
   * unhandled rejection in the console. */
  return new Response(
    JSON.stringify({ offline: true, error: "Not available offline yet." }),
    { status: 503, headers: { "Content-Type": "application/json" } }
  );
}

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response && response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    return new Response("", { status: 503, statusText: "Offline" });
  }
}
