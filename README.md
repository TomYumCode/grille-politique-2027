# grille-politique-2027

Grille des émissions politiques (télévision, radio, YouTube, Twitch, Web) jusqu'au second
tour de la présidentielle 2027. Cahier des charges : `CAHIER_DES_CHARGES.md`.

## Installation

```bash
python3 -m pip install -r requirements.txt
```

## Commandes

```bash
python3 -m grille init            # crée data/grille.sqlite si besoin et lit la configuration
python3 -m grille verifier-acces  # teste le guide XMLTV et les API Radio France, YouTube et Twitch
python3 -m grille collecter-tv    # télécharge le guide TV, garde le politique, écrit en base, affiche la grille
python3 -m grille collecter-tv --motifs   # idem, avec la règle qui a retenu chaque émission
python3 -m grille collecter-agendas  # agendas des partis (meetings, passages dans les médias)
python3 -m grille collecter-annonces # invités annoncés dans les communiqués de France Télévisions
python3 -m grille collecter-radio    # grille des stations Radio France (France Inter, franceinfo, France Culture)
python3 -m grille collecter-youtube  # directs YouTube programmés et en cours des chaînes suivies
python3 -m grille collecter-twitch   # chaînes Twitch en direct et plannings publiés
python3 -m grille collecter       # toutes les sources à la suite ; si l'une tombe, les autres continuent
python3 -m grille lister          # affiche la grille enregistrée (aujourd'hui et les 7 jours suivants)
python3 -m grille chercher-tv "Franc-jeu"   # trouve une émission dans le guide TV et dit si elle est retenue
python3 -m grille page            # génère la page web dans le dossier site/
python3 -m grille apercu          # génère la page et l'affiche sur le téléphone (même Wi-Fi)
python3 -m pytest                 # tests
```

## Voir la page sur le téléphone

Avant la mise en ligne (lot 5), le Mac peut servir la page sur le réseau Wi-Fi :

1. `python3 -m grille collecter` pour remplir la base, puis `python3 -m grille apercu`.
2. La commande affiche une adresse du type `http://192.168.1.20:8000` : l'ouvrir dans
   Safari sur l'iPhone, connecté au même Wi-Fi. Si macOS demande d'autoriser les
   connexions entrantes pour Python, accepter.
3. `Ctrl + C` dans le Terminal pour arrêter.

L'installation sur l'écran d'accueil et le mode hors connexion demandent une adresse
en HTTPS : ils fonctionneront une fois la page publiée sur GitHub Pages (lot 5).

## Clés d'API

Radio France, YouTube et Twitch demandent des clés. Sur ton ordinateur, copie `.env.exemple` en
`.env` (même dossier) et remplis-le : ce fichier est ignoré par Git, il ne sera
jamais publié. Une fois en ligne (lot 5), les mêmes valeurs iront dans les secrets
GitHub.

**YouTube (`YOUTUBE_API_KEY`)**
1. console.cloud.google.com, connecté avec un compte Google ; créer un projet (« grille-politique »).
2. Menu « API et services » → « Bibliothèque » → « YouTube Data API v3 » → « Activer ».
3. « API et services » → « Identifiants » → « Créer des identifiants » → « Clé API ».
4. Conseillé : « Restreindre la clé » → restriction d'API : YouTube Data API v3 seulement.

**Twitch (`TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`)**
1. dev.twitch.tv/console, connecté avec un compte Twitch (l'authentification à deux facteurs est exigée).
2. « Enregistrer votre application » : nom libre, URL de redirection `https://localhost` (Twitch exige HTTPS ;
   elle ne sert pas ici, le champ est seulement obligatoire),
   catégorie « Other », type de client « Confidentiel ».
3. « Gérer » : copier l'identifiant client, puis « Nouveau secret » et copier le secret.

**Radio France (`RADIOFRANCE_API_KEY`)**
1. developers.radiofrance.fr : créer un compte (gratuit, usage non commercial).
2. Une fois connecté, demander une clé (« token ») et la copier.

Vérification : `python3 -m grille verifier-acces` doit afficher quatre `ok`.

## Mise en ligne (GitHub)

Deux tâches tournent toutes seules sur GitHub (onglet **Actions** du dépôt) :

- **Collecte horaire**, chaque heure vers :17 : télévision, radio, YouTube, Twitch, puis
  publication de la page sur `https://tomyumcode.github.io/grille-politique-2027/`.
- **Email du matin**, à 7 h (heure de Paris) : grille du jour, temps forts des 3 jours
  suivants, état des sources.

La base est conservée sur la branche `donnees`, qui ne garde que la dernière version.

### Réglages à faire une fois

1. **Publication de la page** : Settings → Pages → *Build and deployment* → Source :
   **GitHub Actions**.
2. **Secrets** : Settings → Secrets and variables → Actions → *New repository secret*,
   un par ligne :

   | Nom | Valeur |
   | --- | --- |
   | `RADIOFRANCE_API_KEY` | la clé Radio France |
   | `YOUTUBE_API_KEY` | la clé YouTube (comme dans `.env`) |
   | `TWITCH_CLIENT_ID` | l'identifiant client Twitch |
   | `TWITCH_CLIENT_SECRET` | le secret Twitch |
   | `SMTP_SERVEUR` | `smtp.mail.me.com` |
   | `SMTP_UTILISATEUR` | ton adresse iCloud complète (…@me.com) |
   | `SMTP_MOT_DE_PASSE` | un mot de passe d'application iCloud (voir ci-dessous) |
   | `EMAIL_DESTINATAIRE` | l'adresse qui reçoit l'email (un alias « Masquer mon adresse » convient) |

   `SMTP_PORT` (587 par défaut) et `EMAIL_EXPEDITEUR` (= `SMTP_UTILISATEUR` par défaut)
   sont facultatifs.
3. **Mot de passe d'application iCloud** : account.apple.com → *Connexion et sécurité* →
   *Mots de passe pour app* → créer « grille-politique ». Il ne sert qu'à envoyer cet
   email et se révoque à tout moment, sans toucher au mot de passe du compte Apple.

### Premiers essais

- Actions → **Collecte horaire** → *Run workflow* : lance une collecte tout de suite.
  Au bout de quelques minutes, la page est en ligne.
- Actions → **Email du matin** → *Run workflow*, case « Envoyer tout de suite » cochée :
  envoie l'email sans attendre 7 h.
- Sur l'iPhone, ouvrir l'adresse de la page dans Safari, puis Partager → **Sur l'écran
  d'accueil** : la grille s'ouvre en plein écran, même hors connexion.

### À savoir

- Les journaux des tâches sont publics (dépôt public) : ils n'affichent jamais les
  secrets ni l'adresse email.
- GitHub déclenche les tâches planifiées avec quelques minutes de retard, parfois plus.
- GitHub suspend les tâches planifiées d'un dépôt public après 60 jours sans activité,
  en prévenant par email : il suffit alors de les réactiver dans l'onglet Actions.

## Ajouter une chaîne

Ouvrir `config/chaines.yaml` sur GitHub, cliquer sur le crayon, copier une ligne,
l'adapter, puis « Commit changes ».

## Logos des chaînes

Chaque émission affiche le logo de sa chaîne ; le toucher n'affiche plus que cette
chaîne (✕ pour revenir à tout). Les logos viennent des sources : vignette YouTube,
image de profil Twitch, balise `<icon>` du guide TV ; une radio prend le logo de la
chaîne YouTube du même nom. Sans logo, la page affiche les
initiales. Pour imposer un logo, ajouter `logo: "https://…"` à la ligne de la chaîne
dans `config/chaines.yaml`.

## Agendas des partis

Les lignes `plateforme: web` de `config/chaines.yaml` sont des pages d'agenda de partis.
Aujourd'hui : Rassemblement national (meetings et passages des cadres dans les médias,
« Andréa Kotarac sur BFMTV à 17 h ») et UPR (réunions publiques de François Asselineau).
Seuls les rendez-vous qui citent un candidat ou une personnalité suivie sont gardés.
Un passage dans un média rejoint l'émission de la chaîne à cette heure si elle est dans
la grille ; sinon il s'affiche seul, avec l'étiquette « Agenda ».

Chaque site demande son propre lecteur (`grille/agendas.py`). Sans agenda lisible le
11 octobre 2026 : LFI et Reconquête (sites protégés contre les programmes), Renaissance,
LR, Les Écologistes (pas d'agenda), Édouard Philippe (agenda vide ce jour-là).

## Invités annoncés

Le guide télévision ne donne souvent que le titre d'une émission (« Franc-jeu »).
Chaque heure, la collecte lit aussi les communiqués de presse de France Télévisions
(francetvpro.fr), qui annoncent l'invité quelques jours avant : « FRANC-JEU — Roland
Lescure — Dimanche 11 octobre à 13h20 ». L'invité s'ajoute alors à l'émission du même
jour et de la même heure (à 30 minutes près). Les autres chaînes (TF1, M6, BFMTV…)
n'ont pas de page équivalente repérée pour l'instant.

## Doublons entre chaînes

Une même diffusion vue sur plusieurs chaînes (Questions au gouvernement sur LCP et
sur Twitch, un meeting sur la chaîne du candidat et sur celle du parti) ne fait
qu'une carte, avec un logo et un bouton par diffuseur. Règle : chaînes différentes,
débuts à moins de 20 minutes d'écart, et titres qui concordent (`grille/fusion.py`).
La base garde chaque diffusion séparément : la fusion se fait à l'affichage.

## Régler le filtre politique

Tout se passe dans `config/politique.yaml`. Si une émission sans rapport apparaît,
`collecter-tv --motifs` montre la règle responsable : retirer ou préciser le mot-clé,
le déplacer dans `mots_cles_titre` (cherché dans le titre seulement), ou marquer le
parti `ambigu: true`. Si une émission politique manque, `chercher-tv "mot du titre"` montre son titre exact
dans le guide : l'ajouter sous `liste_blanche: emissions:`, éventuellement limitée à
une chaîne (`{titre: "Face à face", chaine: "BFMTV"}`).
