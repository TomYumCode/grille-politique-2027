"use strict";
// Favoris : règles communes à la page et, plus tard, au service de notifications.
// Un favori est une diffusion précise, une émission récurrente, une personne présente,
// ou toute la catégorie « Présidentielle 2027 ».
(function (racine) {
  function normaliser(texte) {
    return (texte || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
      .replace(/[^0-9a-z]+/g, " ").trim();
  }

  // Nom de l'émission récurrente : le titre avant « — » (le reste est le sujet du jour),
  // sans numéro de saison (« C politique S18 »).
  function nomEmission(e) {
    return e.titre.split(" — ")[0].replace(/\s+S\d+$/i, "").trim();
  }

  function cleEmission(e) {
    return normaliser(nomEmission(e)) + "|" + normaliser(e.chaine);
  }

  function vides() {
    return { presidentielle: false, diffusions: [], emissions: [], personnes: [] };
  }

  // Raisons pour lesquelles une émission est un favori (liste vide : ce n'en est pas un).
  function raisons(e, fav) {
    const r = [];
    if (fav.diffusions.includes(e.id)) r.push("cette diffusion");
    const cle = cleEmission(e);
    const emission = fav.emissions.find((x) => x.cle === cle);
    if (emission) r.push("« " + emission.titre + " »");
    for (const nom of e.invites || []) if (fav.personnes.includes(nom)) r.push(nom);
    if (fav.presidentielle && e.campagne) r.push("Présidentielle 2027");
    return r;
  }

  function basculer(liste, valeur, egal = (a, b) => a === b) {
    const i = liste.findIndex((x) => egal(x, valeur));
    if (i >= 0) liste.splice(i, 1); else liste.push(valeur);
  }

  racine.Favoris = { normaliser, nomEmission, cleEmission, vides, raisons, basculer };
})(typeof globalThis !== "undefined" ? globalThis : this);
