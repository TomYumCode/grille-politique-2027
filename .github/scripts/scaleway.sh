#!/usr/bin/env bash
# Publie le site généré (site/) dans le stockage Scaleway (Object Storage, Paris), servi par
# Edge Services sur www.grillepolitique.fr. Lancé par collecte.yml après « Générer la page ».
#   SCW_ACCESS_KEY, SCW_SECRET_KEY : clé de l'application IAM (secrets GitHub)
#   SCW_BUCKET                    : nom du stockage (variable GitHub)
#   SCW_ENDPOINT                  : point d'accès S3 (Paris par défaut ; un autre pour les essais)
# Cache des fichiers, respecté par Edge Services :
#   - page, grille, notifications, service de mise en cache, manifeste : toujours revalidés ;
#   - code et animation (appelés avec leur version « ?v= ») : 5 minutes ;
#   - images et lecteur Lottie : un jour, envoyés seulement s'ils ont changé de taille.
set -euo pipefail
: "${SCW_ACCESS_KEY:?clé Scaleway absente}" "${SCW_SECRET_KEY:?clé Scaleway absente}" "${SCW_BUCKET:?stockage absent}"
export AWS_ACCESS_KEY_ID="$SCW_ACCESS_KEY" AWS_SECRET_ACCESS_KEY="$SCW_SECRET_KEY" AWS_DEFAULT_REGION=fr-par
s3() { aws --endpoint-url "${SCW_ENDPOINT:-https://s3.fr-par.scw.cloud}" s3 "$@" --only-show-errors; }
cible="s3://$SCW_BUCKET"
dossier="${1:-site}"

# 1. Fichiers stables : images, icônes, lecteur Lottie.
s3 sync "$dossier/" "$cible/" --size-only --exclude "*" \
  --include "demarrage/*" --include "icone-*.png" --include "lottie_light.min.js" --include "LICENCE-lottie-web.txt" \
  --cache-control "public, max-age=86400"
# 2. Code, animation et page des sources.
s3 sync "$dossier/" "$cible/" --exclude "*" \
  --include "style.css" --include "app.js" --include "favoris.js" --include "ouverture.json" \
  --include "sources.html" --include "robots.txt" \
  --cache-control "public, max-age=300"
# 3. Ce qui change à chaque collecte : toujours revalidé.
for f in grille.json notifications.json sw.js index.html; do
  s3 cp "$dossier/$f" "$cible/$f" --cache-control "no-cache"
done
s3 cp "$dossier/manifest.webmanifest" "$cible/manifest.webmanifest" --cache-control "no-cache" \
  --content-type "application/manifest+json"
# 4. Tout fichier non prévu ci-dessus, et retrait de ceux qui n'existent plus.
s3 sync "$dossier/" "$cible/" --size-only --delete --cache-control "public, max-age=300"
echo "Site publié sur Scaleway ($SCW_BUCKET)"
