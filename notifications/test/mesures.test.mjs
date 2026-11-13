// Mesure d'audience anonyme : totaux par jour, sans identifiant.
import assert from "node:assert/strict";
import { test } from "node:test";
import service from "../src/index.js";
import { enregistrer, jourParis, nettoyerCompteurs } from "../src/mesures.js";

const PAGE = "https://grillepolitique.fr/";
const ORIGINE = "https://grillepolitique.fr";

function stockage() {
  const kv = new Map();
  return { kv, get: async (k) => (kv.has(k) ? JSON.parse(kv.get(k)) : null), put: async (k, v) => { kv.set(k, v); } };
}

test("compteurs nettoyés : forme, nombre de clés, valeurs", () => {
  assert.deepEqual(nettoyerCompteurs({ "ouverture:installée": 2, "lien:France Inter": 1, "lien:BFMTV": 0,
    "Mal Formé": 3, "lien:<script>": 1, "favori_ajoute": 1.5, "onglet:favoris": 9999 }),
  { "ouverture:installée": 2, "lien:France Inter": 1, "onglet:favoris": 200 });
  assert.deepEqual(nettoyerCompteurs(null), {});
  assert.deepEqual(nettoyerCompteurs(["a"]), {});
  const beaucoup = Object.fromEntries(Array.from({ length: 60 }, (_, i) => ["lien:Chaîne " + i, 1]));
  assert.equal(Object.keys(nettoyerCompteurs(beaucoup)).length, 40);
});

test("jour de Paris (minuit à Paris, pas en UTC)", () => {
  assert.equal(jourParis(Date.parse("2026-11-13T23:30:00Z")), "2026-11-14");
  assert.equal(jourParis(Date.parse("2026-11-13T22:30:00Z")), "2026-11-13");
});

test("totaux du jour, répartis sur plusieurs parts", async () => {
  const s = stockage();
  const midi = Date.parse("2026-11-13T11:00:00Z");
  await enregistrer(s, { "ouverture:installée": 1, "lien:France Inter": 2 }, midi, 0);
  await enregistrer(s, { "ouverture:installée": 1 }, midi, 5);
  await enregistrer(s, { "ouverture:navigateur": 1 }, midi, 0);
  assert.deepEqual(JSON.parse(s.kv.get("mesures:2026-11-13:0")),
    { "ouverture:installée": 1, "lien:France Inter": 2, "ouverture:navigateur": 1 });
  assert.deepEqual(JSON.parse(s.kv.get("mesures:2026-11-13:5")), { "ouverture:installée": 1 });
  assert.equal(await enregistrer(s, { rien: 0 }, midi), false);
});

test("service : envoi depuis la page accepté, autre origine refusée, totaux jamais montrés", async () => {
  const env = { PAGE, ETAT: stockage() };
  const envoi = (origine) => service.fetch(new Request("https://service.example/mesure", {
    method: "POST", headers: { Origin: origine, "Content-Type": "text/plain;charset=UTF-8" },
    body: JSON.stringify({ compteurs: { "ouverture:installée": 1, "onglet:favoris": 2 } }),
  }), env);
  assert.deepEqual(await (await envoi(ORIGINE)).json(), { ok: true });
  assert.equal((await envoi("https://ailleurs.example")).status, 403);
  assert.equal(env.ETAT.kv.size, 1);
  const jour = jourParis(Date.now());
  const r = await service.fetch(new Request("https://service.example/mesures?jour=" + jour), env);
  assert.equal(r.status, 404, "aucune lecture publique des totaux");
});
