#!/usr/bin/env bash
# Espace de stockage (KV) du service de notifications : créé au premier passage, puis
# retrouvé par son nom. Son identifiant est inscrit dans notifications/wrangler.toml juste
# avant la publication (jamais dans le dépôt). Besoin : CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID.
set -euo pipefail
NOM="grille-2027-etat"
API="https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/storage/kv/namespaces"
AUTH="Authorization: Bearer ${CLOUDFLARE_API_TOKEN}"

id=$(curl -fsS -H "$AUTH" "${API}?per_page=100" | jq -r --arg n "$NOM" '.result[] | select(.title == $n) | .id' | head -1)
if [ -z "$id" ]; then
  echo "Création de l'espace de stockage ${NOM}"
  id=$(curl -fsS -X POST -H "$AUTH" -H "Content-Type: application/json" --data "{\"title\":\"${NOM}\"}" "$API" | jq -r '.result.id')
fi
[ -n "$id" ] && [ "$id" != "null" ] || { echo "Espace de stockage introuvable"; exit 1; }
sed -i "s/__ID_KV__/${id}/" notifications/wrangler.toml
echo "Espace de stockage prêt."

sous_domaine=$(curl -fsS -H "$AUTH" "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/workers/subdomain" \
  | jq -r '.result.subdomain // empty' || true)
if [ -n "$sous_domaine" ]; then
  echo "adresse=https://grille-2027-notifications.${sous_domaine}.workers.dev/" >> "${GITHUB_OUTPUT:-/dev/null}"
else
  echo "::warning::Aucun sous-domaine workers.dev : en choisir un dans Cloudflare (Workers & Pages)."
fi
