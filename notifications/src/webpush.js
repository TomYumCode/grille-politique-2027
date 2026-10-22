// Envoi de notifications Web Push (RFC 8030), chiffrées (RFC 8291, « aes128gcm ») et
// signées par une clé VAPID (RFC 8292). Uniquement avec WebCrypto : rien à installer.
// La paire de clés VAPID est créée au premier besoin et gardée dans l'espace de stockage
// du service (KV) : sa partie publique est donnée à la page pour s'abonner.

const ENC = new TextEncoder();
const CLE_VAPID = "vapid";
const VALIDITE_JWT = 3600; // secondes ; Apple refuse les jetons trop longs

export function versB64(octets) {
  let s = "";
  for (const o of new Uint8Array(octets)) s += String.fromCharCode(o);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function depuisB64(texte) {
  const s = atob(texte.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((texte.length + 3) % 4));
  return Uint8Array.from(s, (c) => c.charCodeAt(0));
}

function concat(...parties) {
  const total = parties.reduce((n, p) => n + p.length, 0);
  const r = new Uint8Array(total);
  let i = 0;
  for (const p of parties) { r.set(p, i); i += p.length; }
  return r;
}

async function hmac(cle, donnees) {
  const k = await crypto.subtle.importKey("raw", cle, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", k, donnees));
}

// HKDF (RFC 5869) pour une sortie d'au plus 32 octets : un seul bloc d'expansion.
async function hkdf(sel, ikm, info, longueur) {
  const prk = await hmac(sel, ikm);
  return (await hmac(prk, concat(info, new Uint8Array([1])))).slice(0, longueur);
}

/** Paire VAPID du service : { prive: JWK, publique: base64url de la clé brute (65 octets) }. */
export async function clesVapid(kv) {
  const connues = await kv.get(CLE_VAPID, "json");
  if (connues) return connues;
  const paire = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
  const cles = {
    prive: await crypto.subtle.exportKey("jwk", paire.privateKey),
    publique: versB64(await crypto.subtle.exportKey("raw", paire.publicKey)),
  };
  await kv.put(CLE_VAPID, JSON.stringify(cles));
  return cles;
}

/** Jeton VAPID (JWT ES256) pour le service de notification qui reçoit l'envoi. */
export async function jetonVapid(adresse, sujet, cles, maintenant = Date.now()) {
  const entete = versB64(ENC.encode(JSON.stringify({ typ: "JWT", alg: "ES256" })));
  const contenu = versB64(ENC.encode(JSON.stringify({
    aud: new URL(adresse).origin, exp: Math.floor(maintenant / 1000) + VALIDITE_JWT, sub: sujet,
  })));
  const cle = await crypto.subtle.importKey("jwk", cles.prive, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  // WebCrypto rend la signature au format brut r || s, celui qu'attend un JWT.
  const signature = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, cle, ENC.encode(entete + "." + contenu));
  return entete + "." + contenu + "." + versB64(signature);
}

/** Corps chiffré (aes128gcm, un seul enregistrement) pour l'abonnement { p256dh, auth }. */
export async function chiffrer(message, cles, sel = crypto.getRandomValues(new Uint8Array(16))) {
  const publiqueNavigateur = depuisB64(cles.p256dh);
  const secretAuth = depuisB64(cles.auth);
  const ephemere = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
  const publiqueService = new Uint8Array(await crypto.subtle.exportKey("raw", ephemere.publicKey));
  const cleNavigateur = await crypto.subtle.importKey("raw", publiqueNavigateur, { name: "ECDH", namedCurve: "P-256" },
    false, []);
  const secretEcdh = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: cleNavigateur },
    ephemere.privateKey, 256));
  // RFC 8291, section 3.4 : clé d'entrée liée aux deux clés publiques et au secret d'authentification.
  const ikm = await hkdf(secretAuth, secretEcdh,
    concat(ENC.encode("WebPush: info\0"), publiqueNavigateur, publiqueService), 32);
  const cek = await hkdf(sel, ikm, ENC.encode("Content-Encoding: aes128gcm\0"), 16);
  const nonce = await hkdf(sel, ikm, ENC.encode("Content-Encoding: nonce\0"), 12);
  const cleAes = await crypto.subtle.importKey("raw", cek, "AES-GCM", false, ["encrypt"]);
  // Dernier (et seul) enregistrement : le message suivi du délimiteur 0x02, sans bourrage.
  const clair = concat(typeof message === "string" ? ENC.encode(message) : message, new Uint8Array([2]));
  const chiffre = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, cleAes, clair));
  const taille = new Uint8Array(4);
  new DataView(taille.buffer).setUint32(0, 4096);
  return concat(sel, taille, new Uint8Array([publiqueService.length]), publiqueService, chiffre);
}

/** Envoie un message (objet sérialisé en JSON) ; renvoie le code HTTP du service de notification. */
export async function envoyer(abonnement, message, cles, sujet, duree = 3600) {
  const corps = await chiffrer(JSON.stringify(message), abonnement.keys);
  const jeton = await jetonVapid(abonnement.endpoint, sujet, cles);
  const reponse = await fetch(abonnement.endpoint, {
    method: "POST",
    headers: {
      Authorization: `vapid t=${jeton}, k=${cles.publique}`,
      "Content-Encoding": "aes128gcm",
      "Content-Type": "application/octet-stream",
      TTL: String(duree),
      Urgency: "high",
    },
    body: corps,
  });
  return reponse.status;
}
