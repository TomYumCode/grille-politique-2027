// Quelles notifications envoyer, et quand. Les favoris suivent les règles de la page
// (grille/modele_page/favoris.js), pour que l'étoile et la notification disent la même chose.
import "../../grille/modele_page/favoris.js";

const F = globalThis.Favoris;
const MINUTE = 60 * 1000;
export const RAPPEL = 15 * MINUTE; // rappel au plus 15 minutes avant le début
export const DEBUT_MAX = 30 * MINUTE; // « en direct » seulement dans la première demi-heure
const OUBLI = 2 * 24 * 60 * MINUTE; // trace d'un envoi gardée deux jours après le début
const ANNONCES_MAX = 4; // lignes d'une notification qui regroupe plusieurs annonces
const JOURS = ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."];

function heureParis(maintenant) {
  const parties = new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", hour: "numeric", hourCycle: "h23" })
    .formatToParts(maintenant);
  return Number(parties.find((p) => p.type === "hour").value);
}

/** Nuit (23 h – 7 h, heure de Paris) : les annonces attendent le matin, pas les rappels. */
export function nuit(maintenant) {
  const h = heureParis(maintenant);
  return h >= 23 || h < 7;
}

// « jeu. 23, 08:20 », à partir de l'heure déjà à l'heure de Paris dans les données.
function quand(e) {
  const [a, m, j] = e.debut.slice(0, 10).split("-").map(Number);
  return `${JOURS[new Date(Date.UTC(a, m - 1, j, 12)).getUTCDay()]} ${j}, ${e.debut.slice(11, 16)}`;
}

function ligne(e) {
  return e.titre + " — " + e.chaine + (e.invites && e.invites.length ? " · avec " + e.invites.join(", ") : "");
}

function enDirect(e, t) {
  const debut = Date.parse(e.debut);
  const fin = e.fin ? Date.parse(e.fin) : debut + DEBUT_MAX;
  return debut <= t && t < fin && t - debut <= DEBUT_MAX;
}

/** Émissions qui correspondent aux favoris, sans les annulées. */
export function suivies(emissions, favoris) {
  return emissions.filter((e) => e.statut !== "annulé" && F.raisons(e, favoris).length > 0);
}

/** Après un changement de favoris : ce qui est déjà connu ne sera pas « annoncé ». */
export function marquerConnues(emissions, favoris, envoyes, maintenant) {
  const r = { ...envoyes };
  for (const e of suivies(emissions, favoris)) {
    if (Date.parse(e.debut) > maintenant) r[e.id] = { ...(r[e.id] || {}), a: 1, t: Date.parse(e.debut) };
  }
  return r;
}

/**
 * Notifications à envoyer maintenant pour un abonné, et sa trace d'envois mise à jour.
 * - annonce : un nouveau favori apparaît dans la grille (regroupées ; jamais la nuit) ;
 * - rappel : au plus 15 minutes avant le début ;
 * - en direct : au début, pour ce qui n'a pas eu de rappel (direct YouTube ou Twitch connu
 *   seulement à son lancement, grille mise à jour trop tard pour le rappel).
 */
export function aEnvoyer(emissions, favoris, envoyes, maintenant) {
  const trace = {};
  for (const [id, x] of Object.entries(envoyes || {})) if (x.t > maintenant - OUBLI) trace[id] = { ...x };
  const messages = [];
  const annonces = [];
  for (const e of suivies(emissions, favoris)) {
    const debut = Date.parse(e.debut);
    const deja = trace[e.id] || {};
    const raison = F.raisons(e, favoris).join(", ");
    if (!deja.r && !deja.d && debut > maintenant && debut - maintenant <= RAPPEL) {
      const minutes = Math.max(1, Math.round((debut - maintenant) / MINUTE));
      messages.push({ titre: `Dans ${minutes} min · ${e.chaine}`, corps: ligne(e) + "\n★ " + raison, tag: e.id });
      trace[e.id] = { ...deja, a: 1, r: 1, t: debut };
    } else if (!deja.r && !deja.d && enDirect(e, maintenant)) {
      messages.push({ titre: `En direct · ${e.chaine}`, corps: ligne(e) + "\n★ " + raison, tag: e.id });
      trace[e.id] = { ...deja, a: 1, d: 1, t: debut };
    } else if (!deja.a && debut > maintenant && !nuit(maintenant)) {
      annonces.push(e);
      trace[e.id] = { ...deja, a: 1, t: debut };
    }
  }
  if (annonces.length === 1) {
    const e = annonces[0];
    messages.push({ titre: "Nouveau favori · " + quand(e), corps: ligne(e) + "\n★ " + F.raisons(e, favoris).join(", "),
      tag: "annonce:" + e.id });
  } else if (annonces.length > 1) {
    annonces.sort((x, y) => x.debut.localeCompare(y.debut));
    const lignes = annonces.slice(0, ANNONCES_MAX).map((e) => quand(e) + " · " + e.titre + " (" + e.chaine + ")");
    if (annonces.length > ANNONCES_MAX) lignes.push(`… et ${annonces.length - ANNONCES_MAX} autres`);
    messages.push({ titre: `${annonces.length} favoris annoncés`, corps: lignes.join("\n"), tag: "annonces" });
  }
  const change = messages.length > 0 || Object.keys(trace).length !== Object.keys(envoyes || {}).length;
  return { messages, envoyes: trace, change };
}

/** Favoris reçus de la page, réduits à leur forme attendue (rien d'autre n'est gardé). */
export function nettoyerFavoris(brut) {
  const f = F.vides();
  if (!brut || typeof brut !== "object") return f;
  const textes = (liste, max) => (Array.isArray(liste) ? liste : [])
    .filter((x) => typeof x === "string" && x.length <= 200).slice(0, max);
  f.presidentielle = brut.presidentielle === true;
  f.diffusions = textes(brut.diffusions, 200);
  f.personnes = textes(brut.personnes, 100);
  f.emissions = (Array.isArray(brut.emissions) ? brut.emissions : [])
    .filter((x) => x && typeof x.cle === "string" && typeof x.titre === "string" && x.cle.length <= 300)
    .slice(0, 100).map((x) => ({ cle: x.cle, titre: x.titre.slice(0, 200), chaine: String(x.chaine || "").slice(0, 100) }));
  return f;
}
