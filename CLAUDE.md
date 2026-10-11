# Grille politique Présidentielle 2027

Lire `CAHIER_DES_CHARGES.md`. Le projet avance lot par lot : ne réaliser que le lot
demandé, puis s'arrêter pour faire vérifier le critère « Terminé quand ».

## Consigne permanente

Écrire un test par collecteur à partir d'une réponse enregistrée de la source
(`tests/reponses/`), pour repérer tout de suite un changement de format.

## Repères

- Python 3.11 ou plus ; dépendances dans `requirements.txt` ; tests : `python -m pytest`.
- Configuration modifiable sans code : `config/chaines.yaml` (une ligne par chaîne) et `config/politique.yaml`.
- Base SQLite `data/grille.sqlite` (ignorée par Git), table `emissions`, `chaines_resolues` (identifiants YouTube), `collectes` (comptes rendus), `envois` (emails envoyés), `logos` et `annonces` (`grille/db.py`). Heures en ISO 8601, fuseau Europe/Paris.
- Collecteurs : `grille/tv.py` (lot 2), `grille/youtube.py` et `grille/twitch.py` (lot 3), `grille/radio.py` (API Radio France, après le lot 5), `grille/agendas.py` et `grille/annonces.py` (lot 6). Filtre politique commun : `grille/filtre.py`.
- Lot 6 : agendas des partis (`grille/agendas.py`, lignes `web` de chaines.yaml, un lecteur par site). Appliqué à l'affichage (`grille/affichage.py` : page, email, `lister`), jamais en base : invités annoncés par les communiqués de France Télévisions (`grille/annonces.py`, table `annonces`), passages médias des agendas rattachés à leur émission, puis dédoublonnage (`grille/fusion.py`).
- Page web (lot 4) : `grille/page.py` intègre les données dans `grille/modele_page/index.html` ; sortie dans `site/` (ignoré par Git). Aperçu : `python -m grille apercu`.
- En ligne (lot 5) : `.github/workflows/collecte.yml` (chaque heure, publie la page) et `courriel.yml` (7 h, Paris). Base sur la branche `donnees` (`.github/scripts/base.sh`), jamais dans `main`.
- Secrets en local : fichier `.env` (modèle `.env.exemple`), ignoré par Git.
- Secrets uniquement en variables d'environnement : `RADIOFRANCE_API_KEY` (passe dans l'adresse : toujours la masquer dans les messages), `YOUTUBE_API_KEY`, `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, `SMTP_SERVEUR`, `SMTP_UTILISATEUR`, `SMTP_MOT_DE_PASSE`, `EMAIL_DESTINATAIRE`, plus tard `ANTHROPIC_API_KEY`. Le dépôt est public : aucune adresse email ni clé dans les fichiers.
- Points d'accès et quotas confirmés : `docs/VERIFICATIONS.md`.
- Code, messages et commentaires en français.
