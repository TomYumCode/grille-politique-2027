// Mode hors connexion : réseau d'abord, dernière version enregistrée sinon.
const CACHE = "grille-2027";
const FICHIERS = ["./", "index.html", "sources.html", "style.css", "favoris.js", "app.js", "manifest.webmanifest", "icone-180.png", "icone-192.png",
  "icone-512.png"];

self.addEventListener("install", (ev) => {
  ev.waitUntil(caches.open(CACHE).then((c) => c.addAll(FICHIERS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (ev) => ev.waitUntil(self.clients.claim()));

const LOGOS = "grille-2027-logos";

self.addEventListener("fetch", (ev) => {
  if (ev.request.method !== "GET") return;
  if (new URL(ev.request.url).origin !== location.origin) {
    // Logos des chaînes (YouTube, Twitch, guide TV) : cache d'abord, ils changent rarement.
    if (ev.request.destination !== "image") return;
    ev.respondWith(
      caches.open(LOGOS).then((c) => c.match(ev.request).then((r) => r || fetch(ev.request).then((reponse) => {
        c.put(ev.request, reponse.clone());
        return reponse;
      })))
    );
    return;
  }
  // « no-cache » : toujours demander au serveur si la page a changé (GitHub Pages autorise
  // sinon le navigateur à resservir une version vieille de 10 minutes après une mise à jour).
  ev.respondWith(
    fetch(new Request(ev.request.url, { cache: "no-cache" }))
      .then((reponse) => {
        const copie = reponse.clone();
        caches.open(CACHE).then((c) => c.put(ev.request, copie));
        return reponse;
      })
      .catch(() => caches.match(ev.request, { ignoreSearch: true }).then((r) => r || caches.match("index.html")))
  );
});
