// Le service de bout en bout, avec un faux stockage et un faux réseau.
import assert from "node:assert/strict";
import crypto from "node:crypto";
import { test } from "node:test";
import service, { tournee } from "../src/index.js";
import { versB64 } from "../src/webpush.js";

const PAGE = "https://tomyumcode.github.io/grille-politique-2027/";
const ORIGINE = "https://tomyumcode.github.io";
const APPLE = "https://web.push.apple.com/abc123";

function environnement() {
  const kv = new Map();
  return {
    PAGE,
    kv,
    ETAT: { get: async (k) => (kv.has(k) ? JSON.parse(kv.get(k)) : null), put: async (k, v) => { kv.set(k, v); } },
  };
}

function abonnement() {
  const nav = crypto.createECDH("prime256v1");
  nav.generateKeys();
  return { endpoint: APPLE, keys: { p256dh: versB64(nav.getPublicKey()), auth: versB64(crypto.randomBytes(16)) } };
}

function reseau(emissions, statutPush = 201) {
  const envois = [];
  globalThis.fetch = async (url, options = {}) => {
    const u = String(url);
    if (u.startsWith(PAGE + "notifications.json")) return new Response(JSON.stringify({ emissions }));
    if (u === APPLE) {
      envois.push(options);
      return new Response(null, { status: statutPush });
    }
    throw new Error("adresse inattendue " + u);
  };
  return envois;
}

const poster = (chemin, corps, origine = ORIGINE) => new Request("https://service.example" + chemin, {
  method: "POST", headers: { Origin: origine, "Content-Type": "application/json" }, body: JSON.stringify(corps),
});

const dansDixMinutes = () => {
  const debut = new Date(Date.now() + 10 * 60000);
  // Heure de Paris écrite comme dans les données (le décalage n'importe pas pour Date.parse).
  return { id: "radio:1", titre: "L'invité de 8h20", chaine: "France Inter", plateforme: "radio",
    invites: ["Jordan Bardella"], campagne: "", statut: "annoncé", debut: debut.toISOString(), fin: null };
};

test("abonnement, notification d'essai, rappel, puis abonnement périmé effacé", async () => {
  const env = environnement();
  const emissions = [dansDixMinutes()];
  const envois = reseau(emissions);
  const r = await service.fetch(poster("/abonnement", { abonnement: abonnement(), essai: true,
    favoris: { personnes: ["Jordan Bardella"] } }), env);
  assert.equal(r.status, 200);
  assert.deepEqual(await r.json(), { ok: true, essai: "ok" });
  assert.equal(r.headers.get("Access-Control-Allow-Origin"), ORIGINE);
  assert.equal(envois.length, 1, "notification d'essai");
  assert.match(envois[0].headers.Authorization, /^vapid t=[\w-]+\.[\w-]+\.[\w-]+, k=[\w-]{87}$/);
  assert.equal(envois[0].headers["Content-Encoding"], "aes128gcm");

  assert.deepEqual(await tournee(env), { abonnes: 1, envoyees: 1 }, "rappel 10 minutes avant");
  assert.deepEqual(await tournee(env), { abonnes: 1, envoyees: 0 }, "pas deux fois");

  // Le téléphone a retiré l'abonnement : Apple répond 410, le service l'efface.
  emissions.push({ ...dansDixMinutes(), id: "radio:2" });
  reseau(emissions, 410);
  assert.deepEqual(await tournee(env), { abonnes: 0, envoyees: 0 });
});

test("requêtes refusées : autre origine, adresse étrangère, désabonnement", async () => {
  const env = environnement();
  reseau([]);
  assert.equal((await service.fetch(poster("/abonnement", { abonnement: abonnement() }, "https://pirate.example"), env))
    .status, 403);
  const etranger = { ...abonnement(), endpoint: "https://exemple.com/push" };
  assert.equal((await service.fetch(poster("/abonnement", { abonnement: etranger }), env)).status, 400);
  const a = abonnement();
  assert.equal((await service.fetch(poster("/abonnement", { abonnement: a, favoris: {} }), env)).status, 200);
  assert.equal(Object.keys(JSON.parse(env.kv.get("abonnements"))).length, 1);
  assert.equal((await service.fetch(poster("/desabonnement", { endpoint: a.endpoint }), env)).status, 200);
  assert.deepEqual(JSON.parse(env.kv.get("abonnements")), {});
  const cle = await (await service.fetch(new Request("https://service.example/cle"), env)).json();
  assert.equal(cle.cle.length, 87, "clé publique VAPID (65 octets en base64url)");
});
