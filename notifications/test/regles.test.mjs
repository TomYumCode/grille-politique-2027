import assert from "node:assert/strict";
import { test } from "node:test";
import { aEnvoyer, marquerConnues, nettoyerFavoris, nuit } from "../src/regles.js";

const F = globalThis.Favoris;
// Jeudi 22 octobre 2026, 14 h à Paris (12 h UTC).
const MAINTENANT = Date.UTC(2026, 9, 22, 12, 0);
const e = (id, debut, extra = {}) => ({ id, titre: "L'invité de 8h20", chaine: "France Inter", plateforme: "radio",
  invites: ["Jordan Bardella"], campagne: "", statut: "annoncé", debut, fin: null, ...extra });
const bardella = { ...F.vides(), personnes: ["Jordan Bardella"] };

test("rappel au plus 15 minutes avant, une seule fois", () => {
  const liste = [e("a", "2026-10-22T14:12:00+02:00")];
  const r = aEnvoyer(liste, bardella, {}, MAINTENANT);
  assert.equal(r.messages.length, 1);
  assert.equal(r.messages[0].titre, "Dans 12 min · France Inter");
  assert.match(r.messages[0].corps, /avec Jordan Bardella\n★ Jordan Bardella/);
  assert.equal(aEnvoyer(liste, bardella, r.envoyes, MAINTENANT + 60000).messages.length, 0);
  // Au début : pas de second message, le rappel a suffi.
  assert.equal(aEnvoyer(liste, bardella, r.envoyes, MAINTENANT + 13 * 60000).messages.length, 0);
});

test("direct connu seulement à son lancement : « En direct »", () => {
  const live = [e("yt", "2026-10-22T13:55:00+02:00", { plateforme: "youtube", chaine: "Tocsin", statut: "en direct" })];
  const r = aEnvoyer(live, bardella, {}, MAINTENANT);
  assert.deepEqual(r.messages.map((m) => m.titre), ["En direct · Tocsin"]);
  // Commencé il y a plus d'une demi-heure : trop tard pour prévenir.
  const vieux = [e("yt2", "2026-10-22T13:00:00+02:00", { statut: "en direct" })];
  assert.equal(aEnvoyer(vieux, bardella, {}, MAINTENANT).messages.length, 0);
});

test("annonces d'un nouveau favori, regroupées, jamais la nuit", () => {
  const un = aEnvoyer([e("b", "2026-10-23T08:20:00+02:00")], bardella, {}, MAINTENANT);
  assert.equal(un.messages[0].titre, "Nouveau favori · ven. 23, 08:20");
  const liste = ["23", "24", "25", "26", "27", "28"].map((j) => e("j" + j, `2026-10-${j}T08:20:00+02:00`));
  const plusieurs = aEnvoyer(liste, bardella, {}, MAINTENANT);
  assert.equal(plusieurs.messages.length, 1);
  assert.equal(plusieurs.messages[0].titre, "6 favoris annoncés");
  assert.match(plusieurs.messages[0].corps, /… et 2 autres$/);
  const minuit = Date.UTC(2026, 9, 22, 22, 30); // 0 h 30 à Paris
  assert.ok(nuit(minuit) && !nuit(MAINTENANT));
  const r = aEnvoyer(liste, bardella, {}, minuit);
  assert.equal(r.messages.length, 0);
  assert.equal(aEnvoyer(liste, bardella, r.envoyes, MAINTENANT).messages.length, 1, "annoncées le matin");
});

test("favoris déjà dans la grille au moment de l'abonnement : pas annoncés", () => {
  const liste = [e("c", "2026-10-24T08:20:00+02:00"), e("d", "2026-10-22T14:10:00+02:00")];
  const connues = marquerConnues(liste, bardella, {}, MAINTENANT);
  const r = aEnvoyer(liste, bardella, connues, MAINTENANT);
  assert.deepEqual(r.messages.map((m) => m.titre), ["Dans 10 min · France Inter"]);
});

test("pas de favori, émission annulée, trace oubliée après deux jours", () => {
  assert.equal(aEnvoyer([e("x", "2026-10-22T14:10:00+02:00")], F.vides(), {}, MAINTENANT).messages.length, 0);
  assert.equal(aEnvoyer([e("y", "2026-10-22T14:10:00+02:00", { statut: "annulé" })], bardella, {}, MAINTENANT)
    .messages.length, 0);
  const r = aEnvoyer([], bardella, { vieux: { a: 1, t: MAINTENANT - 3 * 86400000 } }, MAINTENANT);
  assert.deepEqual(r.envoyes, {});
  assert.ok(r.change);
});

test("favoris reçus réduits à leur forme", () => {
  const f = nettoyerFavoris({ presidentielle: "oui", personnes: ["A", 3, "x".repeat(500)], intrus: 1,
    emissions: [{ cle: "c|f5", titre: "C politique", chaine: "France 5", script: "<x>" }, { cle: 1 }] });
  assert.deepEqual(f, { presidentielle: false, diffusions: [], personnes: ["A"],
    emissions: [{ cle: "c|f5", titre: "C politique", chaine: "France 5" }] });
});
