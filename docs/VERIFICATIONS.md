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


Validation (11 octobre 2026), d'après la base de la branche `donnees` et les journaux
GitHub Actions : table `envois` = 2026-10-10 07:00:14 et 2026-10-11 07:00:13 (heure de
Paris) ; 27 collectes horaires réussies du 10 octobre 7 h 31 au 11 octobre 7 h 32, toutes
suivies de la publication Pages ; « quota consommé : 142 unités » par collecte.

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

Clé reçue le 12 octobre 2026 (courriel de Radio France) : limite de 1 000 requêtes par
jour, clé en en-tête `X-Token` ou paramètre `x-token`. Avec la vraie clé :
`verifier-acces` accepte la clé et reconnaît les 3 stations ; une requête `grid` de 8 jours
est refusée (« You can't retrieve more than 24hours »). Le collecteur demande donc un jour
par requête (moins d'une seconde sous 24 h ; deux requêtes le jour de 25 h du passage à
l'heure d'hiver) : aujourd'hui, demain et un des jours suivants à tour de rôle, soit
3 stations × 3 jours × 24 collectes = 216 requêtes par jour.

Restent à vérifier : le champ `diffusion { show { title } }` (nom de l'émission ; le
collecteur s'en passe et le signale s'il est refusé), les adresses « direct » de
`config/chaines.yaml` et la réponse enregistrée `tests/reponses/radiofrance_api.json`,
reconstituée.

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

## Radios privées (12 octobre 2026)

Sites sondés depuis GitHub Actions :

| Site | Résultat |
| --- | --- |
| rtl.fr/grille/JJ-MM-AAAA | une page par jour, environ deux semaines à l'avance (≈ 1,4 Mo) ; cartes `div.programme-card` (`programme-card__time` « 07h00 - 09h00 », `programme-card__title`, `programme-card__description`) et chroniques `li.programme-card__chronique` (`programme-card__chronique-time` « 07h40 », `-title`, `-description`) ; après minuit, la page continue sur le lendemain |
| europe1.fr/grille-des-programmes | semaine type sans dates ni invités : panneaux `section#panel-lundi`… ; `horaires-item-programme` / `title-item-programme`, `horaires-item-chronique` / `title-item-chronique` |
| sudradio.fr/programmes (`?week=1` : semaine suivante) | un panneau par jour titré `h2.sud_planning_titre_jour` « lundi 12 octobre » ; `li.sud_planning_ligne` (`program-start`, `program-end`, `sud_planning_program_name`, `sud_planning_extrait` « Au programme : … ») et chroniques `article.sud_podcast_chronique` (`sud_podcast_chronique_hour`, lien, description) ; la semaine suivante peut être vide |
| rmc.bfmtv.com/grille-radio/ | semaine en cours, sans invités ni résumés : jours titrés `h2.day_title` (« lundi »…), puis un bloc `div.grille_programmes` par jour dans le même ordre ; `article.grille_hours_content` (classe `current` en plus pour l'émission en cours), `grille_date` « 6:54 » (début seul), `h3.grille_title`, lien vers les replays. Relevé le 12 octobre |
| radioclassique.fr/grille-des-programmes/AAAA-MM-JJ/ | une page par jour, semaine précédente et suivante ; lignes `div.timeline__block__row` (`<time datetime="…+00:00">` en UTC, titre en lien, animateur « par … », `span.episode_title` : sujet ou invité du jour) et chroniques `timeline__block__content__sub_item` (« L'invité de la matinale » à 8 h 15). Relevé le 12 octobre |
| nova.fr | pas de grille ; podcasts (podcasts.nova.fr/radio-nova-2027-raisons-de-voter) |

Essai réel du collecteur : 3 radios, 5 pages, 604 programmes à venir, 23 retenus (L'invité
RTL de 7h40, Face à Fogiel, La Grande interview Europe 1 - CNews, L'invité politique Sud
Radio, Le grand débat des Vraies Voix…), aucun journal retenu. Extraits réels dans
`tests/reponses/radio_rtl.html`, `radio_europe1.html`, `radio_sudradio.html`, `radio_rmc.html`,
`radio_radioclassique.html`.

Essai réel avec RMC et Radio Classique (12 octobre, 15 h 53) : 5 radios, 10 pages,
661 programmes à venir, 27 retenus dont « Face à Face » sur RMC du lundi au vendredi,
aucune anomalie. L'invité de la matinale de Radio Classique (Anne Goscinny le
13 octobre) n'est retenu que s'il est une personnalité suivie ; sinon il est compté parmi
les cas douteux, comme « L'édito politique ».

## RTL en direct, Radio Courtoisie, Mediapart (13 octobre 2026)

Sondés depuis GitHub Actions :

- rtl.fr/grille/JJ-MM-AAAA pendant la journée : la carte de l'émission en cours
  (`programme-card programme-card--direct`) n'a pas d'horaire ; ses chroniques sont listées
  normalement. Le lecteur l'ignorait : le 13 octobre à 7 h 36, « L'invité RTL de 7h40 » et
  « Face à Fogiel » sont passés en « annulé ». Corrigé (début à la fin de la carte
  précédente, fin au début de la suivante). Les liens des chroniques mènent à la page de
  l'émission (`rtl.fr/programmes/l-invite-de-7h40`), pas à l'épisode : la page de
  l'émission propose la réécoute.
- rc.fr (Radio Courtoisie, ex-radiocourtoisie.fr) : grille-type en PDF (`rc.fr/grille.pdf`) ;
  la page « filtre par date » ne contient aucun horaire (remplie par le navigateur). La
  matinale « Ligne Droite » (7 h – 9 h 40) est suivie par sa chaîne YouTube.
- Mediapart : pas de programme publié (`mediapart.fr/studio` : vidéos et documentaires).
  Sur YouTube, environ un direct par semaine vers 19 h (« Nos révélations sur Jordan
  Bardella - Édition spéciale », 29 septembre ; débat Coquerel – Ridel, 22 septembre),
  publié au moment du direct : il n'apparaît dans la grille que pendant sa diffusion.

## Invités annoncés par les chaînes (13 octobre 2026)

Sondés depuis GitHub Actions : aucun site n'annonce ses invités à l'avance. RTL
(`/programmes/l-invite-de-7h40`, `/programmes/le-grand-jury`), TF1 Info / LCI et franceinfo
publient des articles après l'émission (« Invité de RTL ce mardi 13 octobre, … ») ; Sud
Radio (`/emission/linvite-politique-sud-radio`) nomme l'invité du jour le matin même ;
BFMTV, Europe 1 et France Inter : descriptions générales ; LCP, Public Sénat, CNews : pas de
page de programme utilisable. En revanche, l'API Radio France donne les invités de France
Inter dès la veille au soir dans le titre de la diffusion (« L'Invité de 7h50 — Natacha
Polony », publié à 19 h 36 le 13 octobre pour le 14), et la grille RTL du jour présente
l'invité dans la description de la chronique.

## Déclenchements programmés de GitHub (16 octobre 2026)

Les tâches programmées de GitHub sont « au mieux » : du 13 au 16 octobre, la collecte
horaire n'a été lancée que toutes les 3 à 5 heures, et aucun des deux déclenchements de
l'email du 16 octobre n'a eu lieu. Parade : deux occasions de collecte par heure (:17 et
:47, la seconde ne refait rien après une collecte de moins de 40 minutes) ; email avec une
occasion toutes les 20 minutes de 6 h à 10 h (heure de Paris), qui s'arrête dès que l'email
du jour est parti et collecte juste avant l'envoi. Commandes ajoutées : `collecte-recente`,
`envoi-du-jour`.

Constat du 16 octobre au soir : malgré les deux occasions par heure, aucune collecte entre
14 h 32 et 19 h (heure de Paris). Les tâches programmées restent donc peu fiables l'après-midi.

Le 17 octobre, sur les quinze occasions d'email de 6 h à 10 h 40, GitHub n'en a lancé
qu'une, à 10 h 21, que l'outil a jugée trop tardive : pas d'email. Désormais l'email part
même en retard, avec des occasions jusqu'à 18 h 40.

## Créneaux Radio France encore vides (16 octobre 2026)

« Questions du soir : le débat » (France Culture, 18 h 20) manquait à la grille le
16 octobre. Sondage de l'API : un créneau de diffusion à venir est renvoyé sans diffusion
(`"diffusion": null`, aucun autre champ sur `DiffusionStep` que `id`, `start`, `end` et
`children`, vide) ; Radio France ne relie la diffusion qu'au dernier moment, le jour même
et parfois pendant l'émission (celle du 13 octobre n'a été vue qu'à 18 h 38). Le collecteur
ignorait ces créneaux. Désormais un créneau vide prend le nom de l'émission diffusée à la
même heure sept jours plus tôt (une requête de plus par station et par jour concerné) ;
le titre de la diffusion le remplace dès qu'il est publié. Réponses enregistrées :
`tests/reponses/radiofrance_creneaux_vides.json`.

## Direct LCP / Public Sénat (17 octobre 2026)

L'adresse https://www.france.tv/lcp-public-senat/direct.html est valide (page « LCP - Public
Sénat en direct TV »), et l'application France TV revendique toutes les adresses de
france.tv (fichier apple-app-site-association). Mais sur iPhone, elle s'ouvre alors sur son
accueil, pas sur le direct. Les deux chaînes ont chacune leur direct sur leur site, lu dans
le navigateur : https://lcp.fr/direct-lcp-5434 et https://www.publicsenat.fr/direct
(réponse 200 toutes les deux). La grille propose donc deux boutons, « Direct LCP » et
« Direct Public Sénat ».

## Allocution présidentielle du 18 octobre 2026

Annoncée par l'Élysée le jour même pour 20 h. Le guide XMLTV (dernière mise à jour à
4 h 16, heure de Paris) annonçait « JT 20h » sur TF1 et « Journal 20h00 » sur France 2,
rien d'autre : aucune source automatique ne connaît un événement décidé dans la journée.
Ajouté : `config/evenements.yaml` (événements à la main), Emmanuel Macron dans les
personnalités, « allocution » dans les mots-clés du titre. La fusion distingue désormais
une chaîne par son nom et sa plateforme (franceinfo télévision et radio : une carte).

## Invités du soir sur BFMTV (21 octobre 2026)

Natacha Polony était en direct sur BFMTV vers 22 h. Le guide XMLTV n'annonçait que
« BFM Grand Soir » (21 h – minuit), sans description ni invité : impossible à repérer à
l'avance. Le relevé des cas douteux a montré six rendez-vous politiques jamais retenus,
faute d'invité nommé : « BFM Politique » et « Le grand oral 2027 » (BFMTV), « 100%
Politique » (CNews), « L'invité politique » (franceinfo), « C politique » (France 5),
« Parlement hebdo » (LCP). Ajoutés à la liste blanche. Écartées sur décision (émissions de
plateau généralistes, souvent politiques mais trop chargées) : « C dans l'air », « C à vous »,
« C ce soir », « 28 minutes », « L'heure des pros », « BFM Grand Soir », « 100% Mabrouk ».

## Notifications (22 octobre 2026)

Web Push : page installée sur l'écran d'accueil de l'iPhone (iOS 16.4 ou plus), abonnement
auprès d'Apple, envoi par un Cloudflare Worker (offre gratuite : 100 000 requêtes par jour,
espace KV à 1 000 écritures par jour, déclencheurs programmés). La tournée toutes les 5
minutes fait une lecture KV et au plus une écriture (seulement si une notification part ou
si la trace change). Chiffrement aes128gcm (RFC 8291) vérifié avec la bibliothèque de
référence `http_ece` 1.2.1, jeton VAPID ES256 (RFC 8292) vérifié par le module crypto de
Node ; service essayé dans le moteur de Cloudflare (`wrangler dev`, wrangler 4.152.0) :
clés, chiffrement et signature fonctionnent. Jeton VAPID valable une heure, sujet = adresse
de la page (pas d'adresse email dans le dépôt). Abonnements acceptés seulement vers les
services de notification des navigateurs (Apple, Google, Mozilla, Microsoft).

## Sujet du jour sur france.tv (22 et 23 octobre 2026)

« C ce soir » du 22 octobre (« LFI - gouvernement : la stratégie de la tension ? »)
manquait : le guide XMLTV ne donne qu'une description générale, la même chaque soir. La
page du direct (https://www.france.tv/france-5/direct.html) donne, pour l'émission à
l'antenne, des données schema.org (VideoObject : nom, description, publication.startDate
et endDate) et un titre `<h2>` (nom de l'émission, puis sujet précédé de « S18 - »). Vérifié
le 23 octobre à 18 h : rien sur les émissions suivantes (pas de liste « à suivre ») ; les
pages des émissions ne listent que les replays. Lecteur : `grille/directs.py`, à chaque
collecte. Réponse enregistrée : `tests/reponses/francetv_direct_france5.html` (« C à vous »).
Constat au passage : « Bompard » seul faisait d'Alexandre Bompard (Carrefour) Manuel
Bompard (LFI) ; un nom de famille seul précédé d'un autre prénom ne compte plus
(`FiltrePolitique.sans_homonymes`).

## Parties d'une émission dans la grille Radio France (25 octobre 2026)

La grille de France Culture donnait « L'Esprit public » entier (11 h 00 – 11 h 58) et ses
deux parties (11 h 01 – 11 h 29, 11 h 29 – 11 h 58), toutes sous le même nom d'émission :
deux cartes pour une émission. Même cas pour « Interception » (France Inter, 18 octobre).
Une partie incluse dans l'émission entière du même nom y est désormais fondue
(`radio.sans_parties_incluses`) ; une chronique d'un autre nom dans une matinale reste à
part. Réponse enregistrée : `tests/reponses/radiofrance_parties_incluses.json`.

## LCI, soir du 25 octobre 2026

Natacha Polony puis Julien Odoul sur LCI vers 21 h : le guide annonçait « 20H Haddad »
(20 h – 22 h) sans description, et la page du direct (https://www.tf1info.fr/direct/,
données schema.org) seulement « grand entretien » puis « débat », sans invité. Rien à
repérer. Constat au passage : « Objectif 2027 dimanche » (LCI, 11 h), retenu le 21 octobre
grâce à sa description, avait été annulé le 22 quand le guide l'avait perdue. Désormais une
émission encore au guide à la même heure, sous le même titre, reste dans la grille ; un autre
programme à sa place l'annule. « Objectif 2027 » (LCI) rejoint la liste blanche, Julien Odoul
les personnalités.

## Faux positif « Génération.s » (31 octobre 2026)

« Les Docs du week-end » (TF1, 16 h 10, la country) était retenu : la ponctuation étant
ignorée, le parti « Génération.s » se lisait dans « une nouvelle génération s'approprie… ».
Le parti est désormais « ambigu » : il ne retient plus une émission à lui seul et compte
seulement parmi les cas douteux. Revue de la base : seul autre texte concerné, l'extrait
YouTube de RMC où Ali Rabeh (« maire Génération•s de Trappes ») est l'invité du « Face à face »,
émission elle-même retenue en direct par la liste blanche (BFMTV, RMC).

## « Flo » sur France 2 (1er novembre 2026)

Le film « Flo » (Florence Arthaud, navigatrice) restait dans la grille, avec « à propos de
Nathalie Arthaud » : retenu le 26 octobre, avant le garde-fou des homonymes. Depuis, le filtre
l'écartait, mais la règle « le guide a perdu la description » le gardait. Elle ne joue plus
que si la description du guide a réellement changé ; à description égale, une émission que
le filtre n'accepte plus sort de la grille.

## Collecte rapide toutes les 15 minutes (2 novembre 2026)

Le sujet du jour de « C à vous » (18 h 57) n'était lu qu'à la collecte de 19 h 45. Toutes les
sources au quart d'heure dépasseraient les quotas : Radio France jusqu'à 18 requêtes par
collecte (96 × 18 = 1 728 > 1 000 par jour), YouTube environ 115 unités (112 chaînes ;
96 × 115 > 10 000 par jour) ; le guide télé n'est mis à jour qu'une fois par jour. D'où une
collecte rapide (`collecter-rapide` : pages du direct de france.tv, 3 requêtes, et Twitch) à
:00, :15 et :30, la complète restant à :45. « collecte-recente » ne regarde que la télévision
(collecte complète), pour que la collecte de secours de GitHub passe si la complète manque.

Le 3 novembre, un déclenchement de secours de GitHub prévu à :17 est parti à 10 h 37 et a
refait une collecte complète (la précédente datait de 9 h 45, plus de 40 minutes). Seuil
porté à 55 minutes : un secours retardé ne double plus la complète de cron-job.org, et celui
de :47 passe toujours si la complète de :45 a manqué.

## Séries publiées en vidéos ordinaires sur YouTube (6 novembre 2026)

Les épisodes de « Les Dossiers » (Gaspard G), « Dans les yeux d'Agathe » (franceinfo) et « Les
aspirants » (RTL) n'entraient jamais dans la grille : le collecteur YouTube ne gardait que les
directs et les premières. Listes de lecture relevées par l'API (playlists.list) : « Dans les
yeux d'Agathe » PLg6GanYvTasXMpDNnfw4fDbaSCj_X0jeR (8 vidéos), « Les Aspirants »
PLY8WvIcEK2TM (2), « POURQUOI PRÉSIDENT(E) ? Le podcast spécial 2027 » (TF1 Info)
PLOInMnMM0_fcA_TQw8cdc54Oen0HnUIH4 (13), « LE MEILLEUR CANDIDAT » (Sam Zirah, @SamZirah)
PLW9jTDYMgwgE (2). Pas de liste pour « Les Dossiers » : chaîne suivie en entier, vidéos de
20 minutes et plus (épisode complet du 2 novembre : 46 min 11 ; extraits des jours suivants :
1 à 2 minutes). Coût : 1 unité par liste et par collecte ; la durée (contentDetails) est lue
dans le même appel videos.list. Réponses enregistrées : `tests/reponses/youtube_episodes.json`.

## Chaînes suivies en entier : HugoDécrypte, Thinkerview, Konbini, Brut, LEGEND (6 novembre 2026)

L'interview d'Emmanuel Macron par HugoDécrypte (28 octobre 2026, 1 h 21, xRIw-ZmDzj4) est sur
une deuxième chaîne, « HugoDécrypte - Grands formats » (UCUo1RqYV8tGjV38sQ8S5p9A,
@hugodecryptegrandsformats), que la grille ne suivait pas ; « HugoDécrypte - Actus du jour »
(UCAcAnMF0OrCtUep3Y4M-ZPw) ne publie que des vidéos courtes. Relevé des 50 dernières vidéos par
chaîne (playlistItems + videos.list), filtre appliqué aux vidéos de 20 minutes et plus :
Grands formats, 3 retenues sur 9 (Macron ; Fabrice Arfi, titre qui cite Bardella ; ministre de
l'Éducation nationale), écartées : Vincent Lindon, Bigflo et Oli, Zendaya, reportages ;
Thinkerview, que des directs (déjà suivis) ; Konbini, Brut, LEGEND : aucune vidéo politique ces
derniers jours, rien de retenu. Aucun coût de plus : les vidéos de la chaîne sont déjà lues
pour les directs.
Directs de Thinkerview écartés faute de nom dans la liste (Agnès Pannier-Runacher, 25 mars ;
François-Xavier Bellamy, 23 octobre 2025 ; Arnaud Montebourg, 12 mai ; Jean Messiha, 15 janvier) :
ces quatre personnalités sont ajoutées à `config/politique.yaml` ; leurs titres sont désormais
retenus, « Matt Bellamy » (Muse) ne l'est pas.

## Sigles de deux lettres (7 novembre 2026)

Alias « PS », « RN » et « R! » ajoutés à la main dans `config/politique.yaml`. Cherchés comme des
mots ordinaires, « PS » et « RN » faisaient entrer « PS : abonnez-vous » (fin de description
YouTube), « PS Plus » (jeux vidéo) et « la RN 7 » (route nationale), et « R! » devenait la lettre
« r » seule. Un sigle de deux lettres au plus compte désormais seulement dans le titre, écrit tel
quel (majuscules comprises), sans chiffre ni « Plus » juste après (`grille/filtre.py`).

## Radio France dans la collecte rapide (9 novembre 2026)

Le 8 novembre, Radio France a renommé la diffusion de Franc-jeu en « Le député Laurent
Wauquiez, invité de Franc-Jeu » au début de l'émission ; la collecte de l'heure suivante l'a
vue. La collecte rapide (:00, :15, :30) relit désormais la journée en cours, de 6 h à 23 h :
3 stations × 17 heures × 3 = 153 requêtes par jour (306 si des créneaux sont encore vides),
plus 216 à 432 pour les collectes complètes : au plus 738 requêtes, sous la limite de 1 000.

## Invité cherché sur le web par Claude (9 novembre 2026)

API Messages d'Anthropic avec l'outil de recherche web (`web_search_20260209`, filtrage des
résultats ; `web_search_20250305` pour Haiku), SDK Python `anthropic` 2.6.0 (paramètres
`fallbacks` et `betas` vérifiés dans le SDK installé). Réponse de test construite d'après le
format documenté (`tests/reponses/claude_invite_grand_oral.json`) : à remplacer par une
réponse réelle enregistrée dès que la clé `ANTHROPIC_API_KEY` est en place.

Volume relevé du 2 au 8 novembre 2026 : 18 à 27 émissions de télévision et de radio par jour,
presque toutes sans invité connu ; les émissions à invité (liste blanche, interview ou débat,
ou titre « L'invité… ») en font 6 à 10 par jour. Coût estimé par question (Claude Opus 5.5,
effort bas, une à trois recherches) : de 0,05 à 0,15 $ ; soit 10 à 35 $ par mois. Avec
`claude-haiku-5-5` : environ 0,02 à 0,04 $ par question (surtout le prix des recherches,
10 $ les 1 000), soit 4 à 10 $ par mois. Plafond par défaut : 12 questions par jour.

## Clé YouTube publiée par un message d'erreur (9 novembre 2026)

GitHub (« secret scanning ») a signalé la clé YouTube dans `grille.sqlite` (branche
`donnees`) : le 16 octobre 2026, une erreur 500 de YouTube sur une chaîne a été enregistrée
dans le compte rendu de collecte avec l'adresse complète de la requête, où passe la clé
(`…&key=…`), et affichée dans le journal public de la tâche. Corrigé : le client YouTube
masque la clé dans toute erreur, `db.noter_collecte` masque toute clé reconnaissable
(`key=`, `x-token=`, `AIza…`, `sk-ant-…`) et l'ouverture de la base efface celles déjà
enregistrées. La clé exposée doit être remplacée dans Google Cloud.

## Grandes émissions à surveiller (9 novembre 2026)

Marine Tondelier, invitée du 20 h de TF1 le 9 novembre 2026, annoncée sur sa page Facebook et
par TF1info (article de 15 h 50) : ni le guide (journal écarté par le filtre, invité jamais
nommé) ni la recherche par Claude (limitée aux émissions déjà dans la grille) ne pouvaient le
voir. Surveillance des 20 h de TF1 et France 2 : deux questions par émission et par jour
(17 h, puis 19 h 50), soit 4 de plus par jour ; plafond porté à 16. Haiku 5.5 : outil de
recherche de base (`web_search_20250305`) et pas de modèle de repli (`fallbacks` réservé à
Opus, Sonnet et Fable).

## Comparaison Haiku 5.5 et Sonnet 5.5 (11 novembre 2026, 8 h 42 – 8 h 48)

`python -m grille comparer-modeles` (tâche « Essai des modèles Claude ») sur les 14 essais de
`docs/essais_recherche.yaml`, une question par essai et par modèle, 1,80 $ au total (Haiku 0,35 $, Sonnet 1,45 $) :

| Modèle | Justes (invité connu) | Coût moyen par question |
| --- | --- | --- |
| `claude-haiku-5-5` | 6 sur 10 | 0,025 $ |
| `claude-sonnet-5-5` | 4 sur 10 | 0,104 $ |

- Trouvés après coup par Haiku, manqués en direct le 10 novembre : Dominique de Villepin
  (Face à face), Marie-Hélène Thoraval (Sud Radio, absente de la liste ce matin-là).
- Manqués par les deux modèles, même après coup : les invités de 7 h 40 (franceinfo, RTL) et de
  8 h 10 (Europe 1) du 10 novembre. Le 10 au matin, la recherche en direct avait pourtant trouvé
  Charles Alloncle (RTL) : d'un essai à l'autre, les réponses varient.
- Face à face du 11 novembre : Édouard Geffray trouvé par Sonnet seul (message de
  @BFMTV_Inside), pendant l'émission.
- Sud Radio du 11 novembre : Haiku répond Marion Maréchal (message de sa part, publié la veille
  à 12 h 14), juste (confirmé ensuite sur le site de Sud Radio) ; la recherche en direct de
  8 h 45 n'avait rien trouvé.

Invités absents de la liste (11 novembre 2026) : retenus désormais quand Claude leur donne une
fonction politique (`accepter_fonctions: true` de config/recherche.yaml). Claude répond pour
chaque invité un nom et sa fonction ; une fonction qui contient un mot de `fonctions_politiques`
(politique.yaml) ou le nom d'un parti (trois lettres au moins) fait retenir le nom, qui est
signalé dans l'email pour l'ajouter à la liste. La fonction s'affiche à côté du nom, comme un
sigle. Dominique Sopo (« président de SOS Racisme ») reste écarté.
- Recherche web directe le matin même (moteur de recherche) : aucune des matinales du jour
  n'est encore indexée ; les sites de franceinfo, Europe 1, Sud Radio, RTL et RMC ne sont pas
  joignables depuis l'environnement de développement.

Décision : Haiku 5.5 reste le modèle de la recherche (plus juste et quatre fois moins cher).

## Flux RSS (9 novembre 2026)

Relevé par une sonde GitHub (33 adresses essayées). Répondent avec un flux lisible : franceinfo
politique (`https://www.franceinfo.fr/politique.rss`), Le Monde, Le Figaro, Libération, BFMTV
et RMC politique, 20 Minutes, Le Parisien (pas de date de publication), L'Express, HuffPost, JDD,
L'Obs, TF1info « à la une » (`/feeds/rss-une.xml` ; la rubrique politique renvoie une page
HTML), Public Sénat (`/feed`), LCP (`/rss-actualites.xml`), stephanelarue.com, Programme TV,
Télé Star. Ne répondent pas : Europe 1, RTL, CNews (404), LCI (renvoie vers TF1info),
Le Point (403), Marianne (405), Ozap et Puremédias (410). Le flux TF1info contenait l'annonce
« Présidentielle 2027 : Marine Tondelier invitée du 20H de TF1 ce lundi » (publiée à 15 h 50) :
extrait enregistré dans `tests/reponses/rss_tf1info.xml`.

## Nouveaux candidats dans les flux RSS (9 novembre 2026)

Candidature de Teddy Riner annoncée le 9 novembre 2026 : absent de `politique.yaml`, il n'était
repérable par aucune source (seule la recherche par Claude l'aurait signalé, à sa première
émission). Articles réels enregistrés (`tests/reponses/rss_publicsenat.xml`, `rss_20minutes.xml`,
`rss_leparisien.xml`) : le détecteur le trouve dans 7 articles de 3 flux ; faux noms relevés
sur ces extraits : « Los Angeles » (écarté : lieu) et Yannick Jadot, cité une fois (sous le seuil
de deux articles). Teddy Riner ajouté à `politique.yaml` (sans étiquette).
