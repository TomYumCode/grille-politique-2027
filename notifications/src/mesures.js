// Mesure d'audience anonyme de la grille : des totaux par jour, rien d'autre.
//
// La page compte ses interactions (ouverture, clic sur « Regarder » par chaîne, favori ajouté…)
// et envoie ses totaux une fois par visite (POST /mesure). Le service les ajoute aux totaux du
// jour (heure de Paris), gardés 90 jours. Aucun identifiant, aucune adresse IP, aucune heure :
// impossible de relier deux visites ou de reconnaître quelqu'un. L'email du matin lit les
// totaux de la veille (GET /mesures?jour=AAAA-MM-JJ).
//
// Écritures réparties sur plusieurs clés (« parts ») : deux visites envoyées au même moment
// écrivent rarement la même clé, sans quoi l'une effacerait l'autre (stockage sans verrou).

const PARTS = 8;
const CONSERVATION = 90 * 24 * 3600; // secondes
const MAX_CLES = 40;
const MAX_PAR_CLE = 200;
// « evenement » ou « evenement:précision » (nom de chaîne, onglet…), en clair et court.
const FORME = /^[a-z_]{1,30}(:[\p{L}\p{N} '’.&()/+-]{1,40})?$/u;

/** Garde seulement des compteurs bien formés et raisonnables (le reste est ignoré). */
export function nettoyerCompteurs(compteurs) {
  const propres = {};
  if (!compteurs || typeof compteurs !== "object" || Array.isArray(compteurs)) return propres;
  for (const [cle, valeur] of Object.entries(compteurs)) {
    if (Object.keys(propres).length >= MAX_CLES) break;
    const n = Number(valeur);
    if (FORME.test(cle) && Number.isInteger(n) && n > 0) propres[cle] = Math.min(n, MAX_PAR_CLE);
  }
  return propres;
}

/** « 2026-11-13 », le jour à Paris. */
export function jourParis(ms) {
  return new Intl.DateTimeFormat("fr-CA", { timeZone: "Europe/Paris", year: "numeric", month: "2-digit", day: "2-digit" })
    .format(new Date(ms));
}

export async function enregistrer(stockage, compteurs, maintenant = Date.now(), part = Math.floor(Math.random() * PARTS)) {
  const propres = nettoyerCompteurs(compteurs);
  if (!Object.keys(propres).length) return false;
  const cle = `mesures:${jourParis(maintenant)}:${part}`;
  const totaux = (await stockage.get(cle, "json")) || {};
  for (const [k, n] of Object.entries(propres)) totaux[k] = (totaux[k] || 0) + n;
  await stockage.put(cle, JSON.stringify(totaux), { expirationTtl: CONSERVATION });
  return true;
}

export async function lire(stockage, jour) {
  const totaux = {};
  for (let part = 0; part < PARTS; part += 1) {
    const morceau = (await stockage.get(`mesures:${jour}:${part}`, "json")) || {};
    for (const [k, n] of Object.entries(morceau)) totaux[k] = (totaux[k] || 0) + n;
  }
  return totaux;
}
