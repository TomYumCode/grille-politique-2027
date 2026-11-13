# grille.json

La grille seule, publiée à chaque collecte (toutes les 15 minutes) à côté de la page :
`https://grillepolitique.fr/grille.json`. Écrite par `grille/page.py`
(les mêmes données sont aussi intégrées dans `index.html`, pour le premier affichage).

Lue par la page à chaque ouverture et à chaque retour sur l'application (`rafraichir` dans
`grille/modele_page/app.js`), et demain par l'application qui embarque la page (mode B).
GitHub Pages l'envoie avec `Access-Control-Allow-Origin: *` : une application peut la lire
depuis une autre origine.

Environ 60 Ko (8 Ko compressé, le 13 novembre 2026). Aucune donnée personnelle : favoris et abonnements
restent sur le téléphone et dans le service de notifications.

## Format

`format` vaut 1. Il augmente quand un champ change de sens ou disparaît ; un champ ajouté ne
change pas le format. Un lecteur ignore les champs qu'il ne connaît pas, et ne lit pas un
format plus récent que le sien.

| Champ | Type | Contenu |
|---|---|---|
| `format` | nombre | version du format (1) |
| `genere_le` | texte | heure de la collecte, ISO 8601 avec fuseau de Paris (`2026-11-13T11:15:00+01:00`) |
| `jours` | liste de textes | aujourd'hui et les 7 jours suivants (`2026-11-13`) |
| `candidats` | liste | `{nom, emissions}` : chaque candidat suivi et son nombre d'émissions dans la grille |
| `logos` | objet | nom de chaîne → adresse de son logo |
| `directs` | liste de textes | adresses des directs des stations de radio (bouton « Écouter en direct ») |
| `sigles` | objet | nom → sigle de `config/politique.yaml` (« LFI »), ou fonction trouvée par la recherche web |
| `notifications` | texte | adresse du service de notifications (vide : pas de notifications) |
| `emissions` | liste | les émissions, détaillées ci-dessous, par heure de début |

### Une émission

| Champ | Type | Contenu |
|---|---|---|
| `id` | texte | identifiant stable : `tv:…`, `radio:…`, `youtube:…`, `twitch:…`, `web:…`, `evenement:…`, `recherche:…` |
| `titre` | texte | titre affiché (« Le grand oral 2027 — Raphaël Glucksmann ») |
| `debut`, `fin` | texte | ISO 8601, fuseau de Paris ; `fin` peut être `null` (direct YouTube sans fin annoncée) |
| `plateforme` | texte | `tv`, `radio`, `youtube`, `twitch` ou `web` (agenda d'un parti) |
| `chaine` | texte | nom de la chaîne, de la station ou de la chaîne en ligne |
| `categorie` | texte | `débat`, `interview`, `meeting` ou `analyse` |
| `invites` | liste de textes | personnes présentes (invitées, interviewées, en meeting) |
| `cites` | liste de textes | personnes seulement citées (« À propos de ») |
| `lien` | liste de textes | adresses pour regarder ou écouter (direct, puis page de l'émission) |
| `statut` | texte | `annoncé`, `en direct` ou `terminé` au moment de la collecte |
| `filtre` | texte | pourquoi l'émission est retenue (`liste blanche`, `mots-clés`) |
| `nature` | texte | `episode` pour un épisode de série mis en ligne, sinon vide |
| `campagne` | texte | pourquoi elle est dans « Présidentielle 2027 » (vide : seulement dans « Toute la politique ») |
| `presentation` | texte | radio : phrase de la station qui présente un invité absent de la liste (« Dominique Sopo est l'invité de Céline Landreau »), sinon vide |
| `sources` | liste | seulement pour une émission diffusée sur plusieurs plateformes : `{chaine, plateforme, lien, precision}` pour chacune |

Le statut « en direct » est recalculé par la page d'après l'heure du téléphone : `statut` ne
sert qu'à défaut.
