// Mode hors connexion : réseau d'abord, dernière version enregistrée sinon.
const CACHE = "grille-2027";
const FICHIERS = ["./", "index.html", "sources.html", "style.css", "favoris.js", "app.js", "manifest.webmanifest", "icone-180.png", "icone-192.png",
  "icone-512.png"];

self.addEventListener("install", (ev) => {
  ev.waitUntil(caches.open(CACHE).then((c) => c.addAll(FICHIERS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (ev) => ev.waitUntil(self.clients.claim()));

const LOGOS = "grille-2027-logos";

// Notifications des favoris, envoyées par le service (notifications/, Cloudflare).
// Chaque message reçu doit s'afficher : iPhone coupe l'abonnement sinon.
self.addEventListener("push", (ev) => {
  let m = {};
  try { m = ev.data ? ev.data.json() : {}; } catch (e) { m = { corps: ev.data ? ev.data.text() : "" }; }
  ev.waitUntil(self.registration.showNotification(m.titre || "Grille politique 2027", {
    body: m.corps || "", tag: m.tag || undefined, icon: "icone-192.png", badge: "icone-192.png",
    data: { url: m.url || self.registration.scope },
  }));
});

// Toucher la notification ouvre la grille (ou la ramène au premier plan).
self.addEventListener("notificationclick", (ev) => {
  ev.notification.close();
  const cible = (ev.notification.data && ev.notification.data.url) || self.registration.scope;
  ev.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((fenetres) => {
    const ouverte = fenetres.find((f) => f.url.startsWith(self.registration.scope));
    return ouverte ? ouverte.focus() : self.clients.openWindow(cible);
  }));
});

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
