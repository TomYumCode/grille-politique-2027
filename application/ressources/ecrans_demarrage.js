// Écrans de démarrage de la page installée sur iPhone (apple-touch-startup-image) : la première
// image de l'animation d'ouverture sur son fond (image de départ de .ouverture, style.css), une
// image par taille d'écran. iOS l'affiche
// pendant l'agrandissement de l'icône, à la place de l'écran blanc (ou noir en mode sombre).
// À relancer après un changement de l'image de départ (.ouverture de style.css) :
//   node application/ressources/ecrans_demarrage.js
// (Playwright et Chromium nécessaires ; écrit grille/modele_page/demarrage/*.jpg et affiche les
// lignes <link> à recopier dans index.html.) JPEG plutôt que PNG : le dégradé tricolore du fond
// reste lisse (un PNG réduit à 256 couleurs fait des bandes) et le fichier est léger.
const { chromium } = require("playwright");
const fs = require("fs");
const os = require("os");
const path = require("path");

const MODELE = path.join(__dirname, "..", "..", "grille", "modele_page");
// Largeur × hauteur en points, densité : iPhone en portrait, du SE (1re génération) aux plus récents.
const ECRANS = [
  [320, 568, 2], [375, 667, 2], [414, 736, 3], [375, 812, 3], [414, 896, 2], [414, 896, 3],
  [390, 844, 3], [428, 926, 3], [393, 852, 3], [430, 932, 3], [402, 874, 3], [420, 912, 3], [440, 956, 3],
];

(async () => {
  const navigateur = await chromium.launch();
  // Page de rendu en fichier (une page vide ne peut pas lire les fichiers du disque).
  const rendu = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "demarrage-")), "rendu.html");
  fs.writeFileSync(rendu, `<!doctype html><html><head><link rel="stylesheet" href="file://${MODELE}/style.css"></head>
    <body><div class="ouverture"></div></body></html>`);
  const liens = [];
  for (const [l, h, d] of ECRANS) {
    const page = await navigateur.newPage({ viewport: { width: l, height: h }, deviceScaleFactor: d });
    await page.goto("file://" + rendu, { waitUntil: "load" });
    const nom = `demarrage-${l * d}x${h * d}.jpg`;
    await page.screenshot({ path: path.join(MODELE, "demarrage", nom), type: "jpeg", quality: 88 });
    await page.close();
    liens.push(`<link rel="apple-touch-startup-image" href="demarrage/${nom}" media="(device-width: ${l}px) and `
      + `(device-height: ${h}px) and (-webkit-device-pixel-ratio: ${d}) and (orientation: portrait)">`);
  }
  await navigateur.close();
  console.log(liens.join("\n"));
})();
