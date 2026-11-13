"""Page web : grille statique générée depuis la base, installable sur téléphone (PWA).

Les données sont intégrées dans index.html : la page s'affiche même sans
connexion (dernière version mise en cache par le service worker) et sans
serveur d'application. Elle est régénérée après chaque collecte.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from grille import affichage, db
from grille.campagne import Campagne
from grille.config import Configuration
from grille.filtre import normaliser
from grille.tv import JOURS_AFFICHES, PARIS

MODELE = Path(__file__).resolve().parent / "modele_page"
# Fichiers appelés par index.html avec leur version (« style.css?v=… », empreinte du contenu) :
# le téléphone les garde et les sert sans attendre le réseau (sw.js) ; une nouvelle version
# change l'adresse, donc elle est chargée à la publication suivante.
VERSIONNES = ("style.css", "favoris.js", "app.js", "lottie_light.min.js", "ouverture.json")
SORTIE = Path(__file__).resolve().parent.parent / "site"
CHAMPS = ("id", "titre", "debut", "fin", "plateforme", "chaine", "categorie", "invites", "cites", "lien", "statut",
          "filtre", "nature")
# Ce dont les favoris ont besoin (grille/modele_page/favoris.js), sans les liens ni les résumés.
CHAMPS_NOTIFICATIONS = ("id", "titre", "debut", "fin", "plateforme", "chaine", "invites", "statut", "campagne",
                        "nature")


# Format de grille.json (docs/GRILLE_JSON.md) : à augmenter quand un champ change de sens ou
# disparaît ; un champ ajouté ne change pas le format.
FORMAT_GRILLE = 1


def donnees(connexion, config: Configuration, maintenant: datetime) -> dict:
    """Émissions non annulées d'aujourd'hui (depuis minuit) et des 7 jours suivants."""
    maintenant = maintenant.astimezone(PARIS)
    minuit = datetime.combine(maintenant.date(), datetime.min.time(), PARIS)
    campagne = Campagne(config)
    # « campagne » : motif du classement dans « Présidentielle 2027 », vide sinon.
    emissions = [{**{k: e[k] for k in CHAMPS + ("sources",) if k in e}, "campagne": campagne.motif(e),
                  "presentation": affichage.presentation(e)}
                 for e in affichage.emissions(connexion, minuit, minuit + timedelta(days=JOURS_AFFICHES))]
    # Émissions où le candidat est présent ou seulement cité.
    presents = Counter(nom for e in emissions for nom in e["invites"] + e.get("cites", []))
    chaines = {s["chaine"] for e in emissions for s in e.get("sources") or [e]}
    # Logo imposé dans chaines.yaml d'abord, sinon celui fourni par la source.
    logos = {nom: url for nom, url in db.logos(connexion).items() if nom in chaines}
    logos.update({c.nom: c.logo for c in config.chaines if c.logo and c.nom in chaines})
    return {
        "format": FORMAT_GRILLE,
        "genere_le": maintenant.isoformat(timespec="seconds"),
        "jours": [(maintenant.date() + timedelta(days=i)).isoformat() for i in range(JOURS_AFFICHES)],
        # Le filtre « candidat » propose tous les candidats suivis, avec leur nombre d'émissions.
        "candidats": [{"nom": nom, "emissions": presents[nom]}
                      for nom in sorted((c["nom"] for c in config.candidats), key=normaliser)],
        "logos": logos,
        # Directs des stations de radio : « Écouter en direct », les autres liens radio menant à l'émission.
        "directs": sorted({d for c in config.chaines if c.plateforme == "radio" for d in c.direct}),
        # Sigle de politique.yaml, sinon fonction donnée par la recherche web (« ministre de… »).
        "sigles": {**db.fonctions_trouvees(connexion),
                   **{p["nom"]: p["sigle"] for p in config.candidats + config.personnalites if p.get("sigle")}},
        # Service de notifications (vide : la page ne les propose pas).
        "notifications": config.notifications,
        "emissions": emissions,
    }


def generer(connexion, config: Configuration, maintenant: datetime, sortie: Path = SORTIE) -> Path:
    """Écrit le site complet dans `sortie` et renvoie le chemin de index.html."""
    sortie.mkdir(parents=True, exist_ok=True)
    for fichier in MODELE.iterdir():
        if fichier.is_dir():  # demarrage/ : écrans de démarrage de la page installée sur iPhone
            shutil.copytree(fichier, sortie / fichier.name, dirs_exist_ok=True)
        elif fichier.name != "index.html":
            shutil.copy2(fichier, sortie / fichier.name)
    tout = donnees(connexion, config, maintenant)
    # Version légère relue toutes les 5 minutes par le service de notifications (notifications/).
    legere = {"genere_le": tout["genere_le"],
              "emissions": [{k: e[k] for k in CHAMPS_NOTIFICATIONS if k in e} for e in tout["emissions"]]}
    (sortie / "notifications.json").write_text(json.dumps(legere, ensure_ascii=False, separators=(",", ":")),
                                               encoding="utf-8")
    contenu = json.dumps(tout, ensure_ascii=False, separators=(",", ":"))
    # La grille seule (docs/GRILLE_JSON.md) : relue par la page à chaque ouverture, et demain par
    # l'application qui embarque la page (mode B).
    (sortie / "grille.json").write_text(contenu, encoding="utf-8")
    # « </ » fermerait la balise <script> qui contient les données.
    contenu = contenu.replace("</", "<\\/")
    page = (MODELE / "index.html").read_text(encoding="utf-8")
    for nom in VERSIONNES:
        empreinte = hashlib.sha256((MODELE / nom).read_bytes()).hexdigest()[:10]
        page = page.replace(f'"{nom}"', f'"{nom}?v={empreinte}"')
    page = page.replace("__DONNEES__", contenu)
    (sortie / "index.html").write_text(page, encoding="utf-8")
    return sortie / "index.html"
