# Grille politique Présidentielle 2027

Lire `CAHIER_DES_CHARGES.md`. Le projet avance lot par lot : ne réaliser que le lot
demandé, puis s'arrêter pour faire vérifier le critère « Terminé quand ».

## Consigne permanente

Écrire un test par collecteur à partir d'une réponse enregistrée de la source
(`tests/reponses/`), pour repérer tout de suite un changement de format.

## Repères

- Python 3.11 ou plus ; dépendances dans `requirements.txt` ; tests : `python -m pytest`.
- Configuration modifiable sans code : `config/chaines.yaml` (une ligne par chaîne), `config/politique.yaml` et `config/evenements.yaml` (événements de dernière minute ajoutés à la main, `grille/evenements.py` ; identifiants « evenement:… » jamais annulés par les autres sources).
- Base SQLite `data/grille.sqlite` (ignorée par Git), table `emissions` (`invites` : personnes présentes, `cites` : seulement citées, `resume` : résumé de la source), `chaines_resolues` (identifiants YouTube), `collectes` (comptes rendus), `envois` (emails envoyés), `logos`, `annonces` et `douteux` (`grille/db.py`). Heures en ISO 8601, fuseau Europe/Paris.
- Collecteurs : `grille/tv.py` (lot 2), `grille/youtube.py` et `grille/twitch.py` (lot 3), `grille/radio.py` (API Radio France, après le lot 5), `grille/radios_privees.py` (grilles RTL, Europe 1, Sud Radio, RMC, Radio Classique : lignes radio à adresse web, un lecteur par site), `grille/agendas.py` et `grille/annonces.py` (lot 6), `grille/directs.py` (sujet du jour de l'émission en cours sur les pages du direct de france.tv, publié seulement au début de l'émission). Filtre politique commun : `grille/filtre.py`. Bouton « Présidentielle 2027 » de la page : `grille/campagne.py` (rubrique `presidentielle:` et `campagne: true` de politique.yaml).
- Lot 6 : agendas des partis (`grille/agendas.py`, lignes `web` de chaines.yaml, un lecteur par site). Appliqué à l'affichage (`grille/affichage.py` : page, email, `lister`), jamais en base : invités annoncés par les communiqués de France Télévisions (`grille/annonces.py`, table `annonces`), passages médias des agendas rattachés à leur émission, puis dédoublonnage (`grille/fusion.py`). Cas douteux (`FiltrePolitique.noter_douteux`, table `douteux`) : mesurés dans l'email avant de décider du classement par Claude, jamais ajoutés à la grille.
- Page web (lot 4) : `grille/page.py` intègre les données dans `grille/modele_page/index.html` ; sortie dans `site/` (ignoré par Git). Aperçu : `python -m grille apercu`. Favoris : `grille/modele_page/favoris.js` (règles communes, gardées sur le téléphone).
- En ligne (lot 5) : `.github/workflows/collecte.yml` (chaque heure, publie la page) et `courriel.yml` (7 h, Paris). Base sur la branche `donnees` (`.github/scripts/base.sh`), jamais dans `main`.
- Notifications : `notifications/` (Cloudflare Worker, JavaScript, tests `node --test notifications/test/*.test.mjs`), publié par `.github/workflows/notifications.yml` ; relit `site/notifications.json` (écrit par `grille/page.py`) ; adresse dans `config/notifications.yaml`. Favoris et abonnements dans son espace KV, jamais dans le dépôt.
- Secrets en local : fichier `.env` (modèle `.env.exemple`), ignoré par Git.
- Secrets uniquement en variables d'environnement : `RADIOFRANCE_API_KEY` (passe dans l'adresse : toujours la masquer dans les messages), `YOUTUBE_API_KEY`, `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, `SMTP_SERVEUR`, `SMTP_UTILISATEUR`, `SMTP_MOT_DE_PASSE`, `EMAIL_DESTINATAIRE`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, plus tard `ANTHROPIC_API_KEY`. Le dépôt est public : aucune adresse email ni clé dans les fichiers.
- Points d'accès et quotas confirmés : `docs/VERIFICATIONS.md`.
- Code, messages et commentaires en français.
