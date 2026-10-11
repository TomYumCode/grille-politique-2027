# Vérification des détails techniques (lot 1, 8 octobre 2026)

Le cahier des charges donne de mémoire les quotas, les points d'accès et le flux
XMLTV. Voici ce qui a été confirmé, et d'après quelle source.

Limite de l'environnement de travail : son réseau bloquait developers.google.com,
dev.twitch.tv et xmltvfr.fr. La consultation s'est donc faite par trois voies :
le document de découverte officiel de l'API YouTube, les fichiers source de
XML-TV-Fr sur GitHub, et des recherches web citant les pages officielles.
Chaque ligne indique son niveau de preuve.

## YouTube Data API v3

| Point | Constat | Source | Preuve |
| --- | --- | --- | --- |
| Quota par défaut | 10 000 unités par jour et par projet ; remise à zéro à minuit, heure du Pacifique | [Quota costs](https://developers.google.com/youtube/v3/determine_quota_cost), via recherche | Officielle, citée |
| Coût d'une lecture `list` | 1 unité (`channels`, `playlistItems`, `videos`) | idem et [Getting started](https://developers.google.com/youtube/v3/getting-started) | Officielle, citée |
| Coût de `search.list` | 100 unités, donc à éviter | idem | Officielle, citée |
| Base des appels | `https://youtube.googleapis.com/youtube/v3/` | [Document de découverte](https://www.googleapis.com/discovery/v1/apis/youtube/v3/rest), révision 20261006 | Officielle, lue directement |
| Chaîne par pseudo `@…` | `channels.list` avec `forHandle` | idem | Officielle, lue directement |
| Playlist des vidéos mises en ligne | `contentDetails.relatedPlaylists.uploads` | idem | Officielle, lue directement |
| Directs programmés | `videos.list` avec `part=snippet,liveStreamingDetails` : `snippet.liveBroadcastContent` vaut `none`, `upcoming`, `live` ou `completed` ; `liveStreamingDetails.scheduledStartTime` est en date-heure ISO | idem ; `videos.list` accepte plusieurs `id` | Officielle, lue directement |

Méthode retenue pour le lot 3 : par chaîne, `playlistItems.list` (1 unité), puis
`videos.list` sur les nouvelles vidéos, 50 au plus par appel (1 unité). Pour
110 chaînes et 24 collectes, cela fait environ **5 280 unités par jour**, sous
la limite de 10 000. Résoudre les pseudos `@…` en identifiants (`channels.list`)
ne coûte qu'une fois par chaîne.

Point à surveiller : un direct programmé apparaît-il dans la playlist des vidéos
mises en ligne avant son début ? À vérifier au lot 3 avec une vraie clé.

## Twitch Helix

| Point | Constat | Source | Preuve |
| --- | --- | --- | --- |
| Jeton d'application | `POST https://id.twitch.tv/oauth2/token` avec `client_id`, `client_secret`, `grant_type=client_credentials` (paramètres de formulaire, pas en-têtes) | [Getting OAuth Access Tokens](https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/), via recherche | Officielle, citée |
| En-têtes | `Authorization: Bearer <jeton>` et `Client-Id: <id>` | idem | Officielle, citée |
| Planning d'une chaîne | `GET https://api.twitch.tv/helix/schedule?broadcaster_id=…` ; jeton d'application accepté ; `data.segments[]` avec `start_time`, `end_time`, `title`, `canceled_until`, `is_recurring` ; par défaut, seulement les créneaux à venir | [Scheduling Broadcasts](https://dev.twitch.tv/docs/api/schedule/), via recherche | Officielle, citée |
| État « en direct » | `GET https://api.twitch.tv/helix/streams?user_login=…`, jusqu'à 100 `user_login` répétés par appel | référence de l'API, via recherche | Officielle, citée |
| Login vers identifiant | `GET https://api.twitch.tv/helix/users?login=…`, 100 au plus, paramètre répété (pas de virgules) ; avec un jeton d'application, au moins un paramètre est obligatoire | tutoriels et [forum développeurs Twitch](https://discuss.dev.twitch.tv/t/cannot-get-multiple-users/23429) | Secondaire |

Le planning demande `broadcaster_id`, pas le login : il faudra résoudre les
logins de `chaines.yaml` via `helix/users`. C'est ce que fait déjà
`verifier-acces`.

## Guide télévision XMLTV

| Point | Constat | Source | Preuve |
| --- | --- | --- | --- |
| Flux gratuit | XML TV Fr (projet libre, Apache 2.0) publie `https://xmltvfr.fr/xmltv/xmltv_tnt.xml.gz` | [dépôt racacax/XML-TV-Fr](https://github.com/racacax/XML-TV-Fr), [documentation](https://xmltvfr.fr/docs.php), [ticket 220](https://github.com/racacax/XML-TV-Fr/issues/220) | Projet, citée ; fichier non téléchargé ici |
| Horizon | Configuration par défaut : aujourd'hui + 7 jours (`fetch_policies` de 0 à 7) | `docs/configuration.md` du dépôt | Projet, lue directement |
| Identifiants de chaînes | `TF1.fr`, `France2.fr`, `France3.fr`, `France5.fr`, `M6.fr`, `Arte.fr`, `BFMTV.fr`, `CNews.fr`, `LCI.fr`, `FranceInfo.fr`, `LaChaineParlementaire.fr` (LCP et Public Sénat partagent le canal) | `resources/channel_config/channels_orange.json` et `channels_telerama.json` | Projet, lue directement |
| Solution de repli | xmltv.ch couvre aussi la TNT française, sur environ 12 jours | [linuxfr.org](https://linuxfr.org/users/vmagnin/journaux/script-pour-surveiller-les-chaines-de-la-tnt) | Secondaire |

Reste à confirmer au lot 2 : que le fichier `xmltv_tnt.xml.gz` contient bien ces
11 identifiants. Le test se lance avec `python -m grille verifier-acces` depuis
un réseau ouvert.

## Lot 2 (8 octobre 2026)

Le collecteur suit le format XMLTV standard : `<programme start stop channel>`,
dates `AAAAMMJJhhmmss ±hhmm`, balises `title`, `sub-title`, `desc`. Le site
xmltvfr.fr restait inaccessible depuis l'environnement de développement : le
contenu réel du fichier n'a pas pu être vérifié. `collecter-tv` signale toute
chaîne configurée absente du guide.

Les adresses de direct (`direct:` dans `chaines.yaml`) sont données de mémoire,
à vérifier dans un navigateur.

## Lot 3 (8 octobre 2026)

YouTube, confirmé dans le document de découverte officiel : `playlistItems.list`
renvoie 50 éléments au plus (`maxResults`), `videos.list` et `channels.list`
acceptent plusieurs `id` séparés par des virgules (1 unité par appel),
`liveStreamingDetails` contient `scheduledStartTime`, `actualStartTime`,
`actualEndTime` et `scheduledEndTime`. Il n'existe pas de recherche par adresse
`/c/…` : le collecteur l'essaie comme pseudo `@…` et signale l'échec.

Estimation : 110 chaînes → 110 + 33 = 143 unités par collecte, environ
**3 400 unités par jour**, sous la limite de 10 000.

Restent à vérifier avec de vraies clés (accès réseau bloqué pendant le lot 3) :

- qu'un direct programmé figure dans la playlist des vidéos mises en ligne
  avant son début (comportement constaté couramment, non documenté) ;
- que `helix/schedule` répond 404 pour une chaîne sans planning (traité comme
  un planning vide) ;
- les réponses enregistrées de `tests/reponses/youtube_api.json` et
  `twitch_api.json`, reconstituées d'après la documentation.

## Lot 5 (9 octobre 2026)

Actions GitHub, versions lues dans les dépôts officiels (`action.yml`) :
`actions/checkout@v6`, `actions/setup-python@v6`, `actions/configure-pages@v6`,
`actions/deploy-pages@v5` (Node 24), `actions/upload-pages-artifact@v5`. Le
déploiement Pages exige les permissions `pages: write` et `id-token: write`
(README de `deploy-pages`). Les fichiers de tâches passent `actionlint`.

SMTP iCloud ([Apple, réglages des serveurs iCloud Mail](https://support.apple.com/102525)) :
`smtp.mail.me.com`, port 587, STARTTLS, identifiant = adresse iCloud complète,
mot de passe d'application.

Heure de l'email : GitHub programme en UTC. 7 h à Paris = 5 h UTC en été, 6 h UTC
en hiver ; deux déclenchements à 4 h 30 et 5 h 30 UTC, puis attente jusqu'à 7 h.

## Radios (10 octobre 2026)

API ouverte de Radio France (portail developers.radiofrance.fr, gratuite, usage non
commercial, compte nécessaire). Le portail et l'API n'étaient pas joignables depuis
l'environnement de développement : la forme des requêtes vient du code source d'une
intégration publique qui l'utilise
([radio-france-home-assistant, `api.py`](https://github.com/kamaradclimber/radio-france-home-assistant/blob/main/custom_components/radio_france/api.py)) :

- adresse `https://openapi.radiofrance.fr/v1/graphql?x-token=<clé>` (requête POST GraphQL) ;
- `grid(start: <horodatage Unix>, end: <horodatage Unix>, station: FRANCEINTER)` renvoie
  des étapes `DiffusionStep` (`id start end diffusion { id title standFirst url }`),
  `BlankStep` (`id title start end`) et `TrackStep` (musique, non demandée) ;
- `brands { id title }` liste les stations : FRANCEINTER, FRANCEINFO, FRANCECULTURE,
  FRANCEMUSIQUE, MOUV, FIP.

Restent à vérifier avec la vraie clé : le champ `diffusion { show { title } }` (nom de
l'émission ; le collecteur s'en passe et le signale s'il est refusé), la durée maximale
couverte par une requête `grid` (le collecteur demande 8 jours), le quota, les adresses
« direct » de `config/chaines.yaml` et la réponse enregistrée
`tests/reponses/radiofrance_api.json`, reconstituée.

Radios privées (RTL, Europe 1, RMC, Sud Radio, Radio Nova) : aucune API publique de
grille trouvée ; sites non joignables depuis l'environnement de développement. Elles
restent suivies par leurs chaînes YouTube. Radio Nova : pseudo `@RADIONOVAChannel`
relevé sur un annuaire de radios (OnlineRadioBox), marqué « à confirmer ».

## Invités annoncés (10 octobre 2026)

Sites testés depuis GitHub Actions (non joignables depuis l'environnement de
développement), par une tâche de sonde temporaire :

- `france.tv/france-2/franc-jeu/` : HTTP 200, mais seulement les émissions passées
  (« Franc-jeu — Invité : Gabriel Attal (Renaissance) »), rien sur la prochaine.
- `francetvpro.fr/contenu-de-presse` : HTTP 200, liste des communiqués de presse, les
  plus récents d'abord, une douzaine par page (`?page=0`, `1`…), sans flux RSS. Chaque
  carte : `h4.card__title` (lignes séparées par `<br>`), `div.card__date` (« Dimanche
  11 octobre à 13h20 sur France 2, France Inter et france.tv »), `div.card__text`
  (résumé). Le 10 octobre : 48 cartes lues sur 4 pages, dont « FRANC-JEU / Roland
  Lescure / Invité de Benjamin Duhamel » et « LES 4 VÉRITÉS / Laure Lavalette /
  Invitée de Francis Letellier ». Les filtres par chaîne (`/france-2/all`) ne
  contiennent pas Franc-jeu, classé sous « france.tv la plateforme ».
- `programme-tv.net` et `telerama.fr` : adresses essayées en 404.
- Extrait enregistré : `tests/reponses/francetvpro_liste.html`.

## Agendas des partis (11 octobre 2026)

Sondés depuis GitHub Actions (pages d'accueil, puis liens « agenda » trouvés) :

| Site | Résultat |
| --- | --- |
| rassemblementnational.fr/agenda | lisible : jour, mois, heure, titre (« Andréa Kotarac sur BFM »), type (« Medias »), phrase (« … sera l'invité de BFMTV le dimanche 11 octobre 2026 à 17h. ») |
| upr.fr/agenda | lisible : sections par mois (`id="2026-10"`), cartes `article.AgendaEventCard` (jour, titre, « 15:00 – 18:00 », description, lien) ; attributs `data-astro-cid-…` sur chaque balise |
| edouardphilippe.fr/agenda | page présente, « Aucun événement à venir » |
| actionpopulaire.fr/agenda/national (LFI), ericzemmour.fr/agenda, pcf.fr | HTTP 403, page « Just a moment… » (protection Cloudflare) |
| parti-renaissance.fr, republicains.fr, lesecologistes.fr, lutte-ouvriere.org | pas de page d'agenda (404) ; Renaissance publie seulement des pages d'inscription par événement (utilisateur.parti-renaissance.fr/evenement/…) |
| horizonsleparti.fr/category/agenda | réunions locales de militants, grands événements passés |

Essai réel du collecteur le 11 octobre : 4 passages médias RN et la réunion publique de
François Asselineau du 18 octobre retenus ; réunions de délégations UPR écartées.
