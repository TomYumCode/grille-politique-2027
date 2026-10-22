// Service de notifications de la Grille politique 2027 (Cloudflare Worker).
//
// La page (GitHub Pages) s'y abonne et lui confie ses favoris ; toutes les 5 minutes, il
// relit la grille publiée (notifications.json, écrit à chaque collecte) et envoie les
// notifications dues. Rien d'autre n'est gardé : l'abonnement du téléphone (adresse et clés
// fournies par Apple ou Google), ses favoris et la trace des notifications déjà envoyées.
import { aEnvoyer, marquerConnues, nettoyerFavoris } from "./regles.js";
import { clesVapid, envoyer } from "./webpush.js";

const CLE_ETAT = "abonnements";
const MAX_ABONNEMENTS = 10; // un seul utilisateur : quelques appareils au plus
const TAILLE_MAX = 32 * 1024;
// Services de notification des navigateurs : le service n'envoie à aucune autre adresse.
const SERVICES_PUSH = [/^web\.push\.apple\.com$/, /^fcm\.googleapis\.com$/, /^updates\.push\.services\.mozilla\.com$/,
  /\.notify\.windows\.com$/, /^android\.googleapis\.com$/];

function entetes(env) {
  return {
    "Access-Control-Allow-Origin": new URL(env.PAGE).origin,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
  };
}

function json(env, donnees, statut = 200) {
  return new Response(JSON.stringify(donnees), {
    status: statut, headers: { ...entetes(env), "Content-Type": "application/json; charset=utf-8" },
  });
}

async function identifiant(endpoint) {
  const h = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(endpoint)));
  return [...h.slice(0, 12)].map((o) => o.toString(16).padStart(2, "0")).join("");
}

function abonnementValide(a) {
  try {
    const url = new URL(a.endpoint);
    return url.protocol === "https:" && SERVICES_PUSH.some((r) => r.test(url.hostname))
      && typeof a.keys?.p256dh === "string" && typeof a.keys?.auth === "string"
      && a.keys.p256dh.length < 200 && a.keys.auth.length < 100;
  } catch (e) {
    return false;
  }
}

async function lireGrille(env) {
  const r = await fetch(new URL("notifications.json", env.PAGE) + "?t=" + Date.now(), {
    cf: { cacheTtl: 0 }, headers: { "Cache-Control": "no-cache" },
  });
  if (!r.ok) throw new Error("grille illisible : HTTP " + r.status);
  return (await r.json()).emissions || [];
}

async function lireEtat(env) {
  return (await env.ETAT.get(CLE_ETAT, "json")) || {};
}

async function notifier(env, cles, abonne, message) {
  const statut = await envoyer(abonne.abonnement, { ...message, url: env.PAGE }, cles, env.PAGE);
  // 404 / 410 : abonnement retiré par le téléphone (application supprimée, autorisation coupée).
  return statut === 404 || statut === 410 ? "perime" : statut < 300 ? "ok" : "erreur " + statut;
}

async function recevoir(requete, env) {
  const url = new URL(requete.url);
  if (requete.method === "OPTIONS") return new Response(null, { status: 204, headers: entetes(env) });
  if (requete.method === "GET" && url.pathname === "/cle") {
    return json(env, { cle: (await clesVapid(env.ETAT)).publique });
  }
  if (requete.method === "GET" && url.pathname === "/") return json(env, { service: "Grille politique 2027", ok: true });
  if (requete.method !== "POST") return json(env, { erreur: "inconnu" }, 404);
  if (requete.headers.get("Origin") !== new URL(env.PAGE).origin) return json(env, { erreur: "origine refusée" }, 403);
  const texte = await requete.text();
  if (texte.length > TAILLE_MAX) return json(env, { erreur: "trop long" }, 413);
  let corps;
  try { corps = JSON.parse(texte); } catch (e) { return json(env, { erreur: "JSON illisible" }, 400); }
  const etat = await lireEtat(env);

  if (url.pathname === "/desabonnement") {
    delete etat[await identifiant(String(corps.endpoint || ""))];
    await env.ETAT.put(CLE_ETAT, JSON.stringify(etat));
    return json(env, { ok: true });
  }
  if (url.pathname !== "/abonnement") return json(env, { erreur: "inconnu" }, 404);
  const abonnement = corps.abonnement;
  if (!abonnementValide(abonnement || {})) return json(env, { erreur: "abonnement invalide" }, 400);
  const id = await identifiant(abonnement.endpoint);
  if (!etat[id] && Object.keys(etat).length >= MAX_ABONNEMENTS) return json(env, { erreur: "trop d'abonnements" }, 429);
  const favoris = nettoyerFavoris(corps.favoris);
  const maintenant = Date.now();
  let envoyes = etat[id]?.envoyes || {};
  try {
    // Ce qui est déjà dans la grille n'est pas « annoncé » : seulement rappelé avant le début.
    envoyes = marquerConnues(await lireGrille(env), favoris, envoyes, maintenant);
  } catch (e) { /* grille indisponible : la prochaine tournée fera les annonces */ }
  etat[id] = {
    abonnement: { endpoint: abonnement.endpoint, keys: { p256dh: abonnement.keys.p256dh, auth: abonnement.keys.auth } },
    favoris, envoyes, maj: new Date(maintenant).toISOString(),
  };
  await env.ETAT.put(CLE_ETAT, JSON.stringify(etat));
  let essai = "";
  if (corps.essai) {
    essai = await notifier(env, await clesVapid(env.ETAT), etat[id], {
      titre: "Notifications activées",
      corps: "Rappels 15 minutes avant vos favoris, annonces des nouveaux passages et débuts de direct.",
      tag: "essai",
    });
  }
  return json(env, { ok: true, essai });
}

/** Tournée de toutes les 5 minutes. */
export async function tournee(env, maintenant = Date.now()) {
  const etat = await lireEtat(env);
  if (!Object.keys(etat).length) return { abonnes: 0, envoyees: 0 };
  const emissions = await lireGrille(env);
  const cles = await clesVapid(env.ETAT);
  let modifie = false;
  let envoyees = 0;
  for (const [id, abonne] of Object.entries(etat)) {
    const { messages, envoyes, change } = aEnvoyer(emissions, abonne.favoris, abonne.envoyes, maintenant);
    for (const message of messages) {
      const resultat = await notifier(env, cles, abonne, message);
      if (resultat === "perime") { delete etat[id]; break; }
      if (resultat === "ok") envoyees += 1;
      else console.log("Notification refusée :", resultat);
    }
    if (etat[id]) etat[id].envoyes = envoyes;
    modifie = modifie || change || !etat[id];
  }
  // Une seule écriture, et seulement si quelque chose a changé (quota gratuit : 1 000 écritures par jour).
  if (modifie) await env.ETAT.put(CLE_ETAT, JSON.stringify(etat));
  return { abonnes: Object.keys(etat).length, envoyees };
}

export default {
  async fetch(requete, env) {
    try {
      return await recevoir(requete, env);
    } catch (e) {
      console.log("Erreur :", e && e.stack || e);
      return json(env, { erreur: "erreur du service" }, 500);
    }
  },
  async scheduled(evenement, env, ctx) {
    ctx.waitUntil(tournee(env).then((r) => console.log("Tournée :", JSON.stringify(r))));
  },
};
