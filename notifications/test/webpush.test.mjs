// Chiffrement et signature vérifiés par un code indépendant (module crypto de Node, pas WebCrypto).
import assert from "node:assert/strict";
import crypto from "node:crypto";
import { test } from "node:test";
import { chiffrer, clesVapid, depuisB64, jetonVapid, versB64 } from "../src/webpush.js";

function hkdf(sel, ikm, info, n) {
  return Buffer.from(crypto.hkdfSync("sha256", ikm, sel, info, n));
}

// Déchiffrement aes128gcm (RFC 8188 / RFC 8291) côté navigateur.
function dechiffrer(corps, navigateur, auth) {
  const sel = corps.subarray(0, 16);
  const longueurCle = corps[20];
  const publiqueService = corps.subarray(21, 21 + longueurCle);
  const chiffre = corps.subarray(21 + longueurCle);
  const secret = navigateur.computeSecret(publiqueService);
  const info = Buffer.concat([Buffer.from("WebPush: info\0"), navigateur.getPublicKey(), publiqueService]);
  const ikm = hkdf(auth, secret, info, 32);
  const cek = hkdf(sel, ikm, Buffer.from("Content-Encoding: aes128gcm\0"), 16);
  const nonce = hkdf(sel, ikm, Buffer.from("Content-Encoding: nonce\0"), 12);
  const d = crypto.createDecipheriv("aes-128-gcm", cek, nonce);
  d.setAuthTag(chiffre.subarray(chiffre.length - 16));
  const clair = Buffer.concat([d.update(chiffre.subarray(0, chiffre.length - 16)), d.final()]);
  assert.equal(clair[clair.length - 1], 2, "délimiteur du dernier enregistrement");
  return { texte: clair.subarray(0, clair.length - 1).toString(), taille: corps.readUInt32BE(16), longueurCle };
}

test("message déchiffrable par le navigateur abonné", async () => {
  const navigateur = crypto.createECDH("prime256v1");
  navigateur.generateKeys();
  const auth = crypto.randomBytes(16);
  const message = JSON.stringify({ titre: "Dans 12 min · France Inter", corps: "L'invité de 8h20 — Édouard Philippe" });
  const corps = Buffer.from(await chiffrer(message, { p256dh: versB64(navigateur.getPublicKey()), auth: versB64(auth) }));
  const r = dechiffrer(corps, navigateur, auth);
  assert.equal(r.texte, message);
  assert.equal(r.taille, 4096);
  assert.equal(r.longueurCle, 65);
});

test("jeton VAPID signé ES256, vérifiable avec la clé publique donnée à la page", async () => {
  const kv = new Map();
  const stockage = { get: async (k) => (kv.has(k) ? JSON.parse(kv.get(k)) : null), put: async (k, v) => kv.set(k, v) };
  const cles = await clesVapid(stockage);
  assert.deepEqual(await clesVapid(stockage), cles, "paire créée une seule fois");
  assert.equal(depuisB64(cles.publique).length, 65);
  const maintenant = Date.UTC(2026, 9, 22, 12);
  const jeton = await jetonVapid("https://web.push.apple.com/QGuQyavXutnMH...", "https://exemple.fr/", cles, maintenant);
  const [entete, contenu, signature] = jeton.split(".");
  assert.deepEqual(JSON.parse(Buffer.from(depuisB64(entete))), { typ: "JWT", alg: "ES256" });
  const c = JSON.parse(Buffer.from(depuisB64(contenu)));
  assert.deepEqual(c, { aud: "https://web.push.apple.com", exp: maintenant / 1000 + 3600, sub: "https://exemple.fr/" });
  const publique = crypto.createPublicKey({ key: { ...cles.prive, d: undefined }, format: "jwk" });
  assert.ok(crypto.verify("sha256", Buffer.from(entete + "." + contenu), { key: publique, dsaEncoding: "ieee-p1363" },
    Buffer.from(depuisB64(signature))));
});

test("base64url sans remplissage, aller et retour", () => {
  for (const n of [0, 1, 2, 3, 16, 65]) {
    const octets = crypto.randomBytes(n);
    const b = versB64(octets);
    assert.ok(!/[+/=]/.test(b));
    assert.deepEqual(Buffer.from(depuisB64(b)), octets);
  }
});
