"""Page web : grille statique générée depuis la base, installable sur téléphone (PWA).

Les données sont intégrées dans index.html : la page s'affiche même sans
connexion (dernière version mise en cache par le service worker) et sans
serveur d'application. Elle est régénérée après chaque collecte.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from grille import affichage, db
from grille.config import Configuration
from grille.tv import JOURS_AFFICHES, PARIS

MODELE = Path(__file__).resolve().parent / "modele_page"
SORTIE = Path(__file__).resolve().parent.parent / "site"
CHAMPS = ("id", "titre", "debut", "fin", "plateforme", "chaine", "categorie", "invites", "lien", "statut", "filtre")


def donnees(connexion, config: Configuration, maintenant: datetime) -> dict:
    """Émissions non annulées d'aujourd'hui (depuis minuit) et des 7 jours suivants."""
    maintenant = maintenant.astimezone(PARIS)
    minuit = datetime.combine(maintenant.date(), datetime.min.time(), PARIS)
    emissions = [{k: e[k] for k in CHAMPS + ("sources",) if k in e}
                 for e in affichage.emissions(connexion, minuit, minuit + timedelta(days=JOURS_AFFICHES))]
    presents = {nom for e in emissions for nom in e["invites"]}
    chaines = {s["chaine"] for e in emissions for s in e.get("sources") or [e]}
    # Logo imposé dans chaines.yaml d'abord, sinon celui fourni par la source.
    logos = {nom: url for nom, url in db.logos(connexion).items() if nom in chaines}
    logos.update({c.nom: c.logo for c in config.chaines if c.logo and c.nom in chaines})
    return {
        "genere_le": maintenant.isoformat(timespec="seconds"),
        "jours": [(maintenant.date() + timedelta(days=i)).isoformat() for i in range(JOURS_AFFICHES)],
        # Le filtre « candidat » ne propose que ceux qui apparaissent dans la grille.
        "candidats": sorted((c["nom"] for c in config.candidats if c["nom"] in presents), key=str.casefold),
        "logos": logos,
        "emissions": emissions,
    }


def generer(connexion, config: Configuration, maintenant: datetime, sortie: Path = SORTIE) -> Path:
    """Écrit le site complet dans `sortie` et renvoie le chemin de index.html."""
    sortie.mkdir(parents=True, exist_ok=True)
    for fichier in MODELE.iterdir():
        if fichier.name != "index.html":
            shutil.copy2(fichier, sortie / fichier.name)
    contenu = json.dumps(donnees(connexion, config, maintenant), ensure_ascii=False, separators=(",", ":"))
    # « </ » fermerait la balise <script> qui contient les données.
    contenu = contenu.replace("</", "<\\/")
    page = (MODELE / "index.html").read_text(encoding="utf-8").replace("__DONNEES__", contenu)
    (sortie / "index.html").write_text(page, encoding="utf-8")
    return sortie / "index.html"
