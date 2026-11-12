# Éléments graphiques de l'application

Fichiers vectoriels (SVG) de l'écran d'ouverture retenu, « C bleue » (10 novembre 2026). Le texte
est converti en tracés : les fichiers s'affichent à l'identique sans police installée.

| Fichier | Contenu |
|---|---|
| `ecran-ouverture-c-bleue.svg` | Écran d'ouverture, état final (1170 × 2532, taille d'un iPhone) |
| `ecran-ouverture-c-bleue-anime.svg` | Le même, animé (ondes du point rouge, nom, trait tricolore) : s'ouvre dans un navigateur |
| `icone-application.svg` | Icône d'application, carré plein de 1024 × 1024 (le téléphone arrondit les coins) |
| `logo-grille.svg` | Logo seul, cases blanches sur fond transparent |
| `trait-tricolore.svg` | Trait bleu-blanc-rouge cerné de blanc |
| `ecran-ouverture-anime.json` | Animation d'ouverture V2 du 12 novembre 2026 (After Effects, export Lottie, 1,5 s à 30 images/s, fond transparent ; V1 du 11 novembre : 2 s) |
| `fond-ouverture.webp` | Fond V2 de l'écran d'ouverture (1170 × 2532, d'après `BG_V2.ai` du propriétaire) : bleu nuit en haut, lueur tricolore en bas |

Écran d'ouverture de la grille (et donc de l'application), depuis le 11 novembre 2026 :
- `grille/modele_page/ouverture.json` : copie de `ecran-ouverture-anime.json`, lue par
  `lottie_light.min.js` (lottie-web 5.12.2, licence MIT : `LICENCE-lottie-web.txt`) ; la
  recopier après tout changement ;
- `grille/modele_page/ouverture.svg` : première image de l'animation, affichée tout de suite le
  temps que l'animation se charge (à refaire si la première image change) ;
- le fond est `fond-ouverture.webp`, intégré dans `.ouverture` de `grille/modele_page/style.css`
  (image en base64, affichée dès la première image) ; à réintégrer après tout changement ;
  le logo fixe `TypoLogo_V2.ai` du propriétaire correspond au pixel près à la première image
  de l'animation.

- `grille/modele_page/demarrage/` : écrans de démarrage de la page installée sur iPhone
  (`apple-touch-startup-image`), affichés par iOS pendant l'agrandissement de l'icône au lieu
  d'un écran blanc (noir en mode sombre) ; en JPEG, faits par `ecrans_demarrage.js` (à relancer après un
  changement de `ouverture.svg` ou du fond).

Les SVG « C bleue » ci-dessus restent la référence du logo (première version, logo à 100 %).

Point rouge : 45 % de la case centrale (réduit par le propriétaire le 10 novembre 2026). Couleurs : bleu du fond `#1f3a5f` (`#1f3b5f` dans l'animation et son fond), bleu du drapeau `#2f63d6`, rouge `#d32f2f`, blanc `#ffffff`,
gris clair du trait `#e6ebf3`. Polices : Archivo ExtraBold (nom) et Inter SemiBold (sous-titre),
licence SIL Open Font License, depuis Fontsource.
