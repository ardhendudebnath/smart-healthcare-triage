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
const CACHE_VERSION = "triage-v4";
const SHELL_CACHE = `${CACHE_VERSION}-shell`;
const DATA_CACHE = `${CACHE_VERSION}-data`;

/* Everything needed to render the app with no network at all. */
/* The ?v= values must match index.html exactly. The browser requests
 * "app.js?v=2", so precaching a bare "app.js" would store a URL nothing ever
 * asks for: the cache would look full and every request would still miss. */
const SHELL_ASSETS = [
  "./",
  "./index.html",
  "./styles.css?v=4",
  "./app.js?v=4",
  "./manifest.json",
];

/* Reference endpoints worth keeping. Each is read-only, changes only on
 * deploy, and is useful offline. */
const CACHEABLE_API = ["/symptoms", "/specialties", "/doctors", "/languages"];

/**
 * Cache the shell if it is not already complete. Safe to call repeatedly.
 *
 * Install runs once. If it fails — a flaky connection, a captive portal, a
 * server restarted mid-request — the worker still activates, the caches stay
 * empty, and offline support is off permanently with nothing to say so. The app
 * looks perfectly healthy right up until the network goes away and it will not
 * load at all. Observed exactly that here after an install raced a server
 * restart: the worker reported "activated" with an empty cache.
 *
 * That failure lands hardest on the person this feature exists for. Someone
 * whose first visit happens on a bad connection is the most likely to need the
 * app offline later, and was the least likely to have it.
 *
 * So caching is a repair that re-runs on activate and whenever the page regains
 * connectivity, rather than a one-shot. addAll stays atomic per attempt — a
 * half-cached shell is still worse than none, because it fails in ways nobody
 * can reproduce — but a failed attempt is no longer the end of the story.
 */
async function ensureShellCached() {
  /* The whole body is guarded, not just the addAll. Opening the cache and
   * building the URLs can throw too, and an escaping rejection here used to
   * break the activate chain before clients.claim() ran — leaving a worker that
   * controlled no pages, cached nothing, and still reported "activated". A
   * caching problem must never cost the worker control of the app. */
  try {
    const cache = await caches.open(SHELL_CACHE);
    const cached = await cache.keys();
    const cachedKeys = new Set(
      cached.map((request) => {
        const url = new URL(request.url);
        return url.pathname + url.search;
      })
    );

    const missing = SHELL_ASSETS.filter((asset) => {
      const url = new URL(asset, self.location.href);
      return !cachedKeys.has(url.pathname + url.search);
    });

    if (!missing.length) return true;

    await cache.addAll(SHELL_ASSETS);
    return true;
  } catch (error) {
    console.warn("[sw] could not cache the shell; will retry later:", error);
    return false;
  }
}

self.addEventListener("install", (event) => {
  /* skipWaiting runs whether or not caching worked. A first attempt that failed
   * must still yield an active worker, because every retry path lives on the
   * active one. */
  event.waitUntil(ensureShellCached().then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      try {
        const names = await caches.keys();
        await Promise.all(
          names
            .filter((name) => !name.startsWith(CACHE_VERSION))
            .map((name) => caches.delete(name))
        );
        await ensureShellCached();
      } catch (error) {
        console.warn("[sw] activate housekeeping failed:", error);
      }
      /* Outside the try, and last: claiming the open pages is the one step that
       * must happen every time. Without it the worker controls nothing, so no
       * fetch is intercepted and nothing can be repaired later either. */
      await self.clients.claim();
    })()
  );
});

/* The page posts this when the browser reports the network is back. That is the
 * moment a shell which failed to cache can finally be fetched. */
self.addEventListener("message", (event) => {
  if (event.data === "retry-shell-cache") {
    event.waitUntil(ensureShellCached());
  }
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
