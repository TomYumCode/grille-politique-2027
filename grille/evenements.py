"""Événements ajoutés à la main (config/evenements.yaml) : une allocution présidentielle
annoncée l'après-midi pour le soir même n'est dans aucun guide (le guide télé n'est mis à
jour qu'une fois par jour). Une ligne suffit ; l'événement apparaît sur chaque chaîne citée,
et la fusion n'en fait qu'une carte avec un lien par chaîne.

Les émissions écrites ici (identifiant « evenement:… ») ne sont jamais passées en « annulé »
par les autres collecteurs ; un événement retiré du fichier passe en « annulé ».
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from grille import db
from grille.config import Configuration
from grille.filtre import FiltrePolitique, normaliser
from grille.tv import PARIS, statut

PREFIXE = "evenement:"
DUREE = 30  # minutes, si la ligne ne précise pas « duree »


@dataclass
class Rapport:
    retenues: list[dict] = field(default_factory=list)
    annulees: int = 0
    anomalies: list[str] = field(default_factory=list)


def _debut(valeur) -> datetime:
    """« 2026-10-18 20:00 » (heure de Paris), ou une date-heure déjà lue par YAML."""
    debut = valeur if isinstance(valeur, datetime) else datetime.fromisoformat(str(valeur).strip())
    return debut.replace(tzinfo=PARIS) if debut.tzinfo is None else debut.astimezone(PARIS)


def _chaine(chaines: dict, nom: str):
    """« franceinfo » désigne la télévision ; « franceinfo (radio) » la radio du même nom."""
    m = re.fullmatch(r"(.+?)\s*\((tv|radio)\)", nom.strip(), re.IGNORECASE)
    if m:
        return chaines.get((normaliser(m.group(1)), m.group(2).lower()))
    return chaines.get((normaliser(nom), "tv")) or chaines.get((normaliser(nom), "radio"))


def collecter(config: Configuration, connexion, maintenant: datetime) -> Rapport:
    rapport = Rapport()
    maintenant = maintenant.astimezone(PARIS)
    chaines = {(normaliser(c.nom), c.plateforme): c for c in config.chaines if c.plateforme in ("tv", "radio")}
    filtre = FiltrePolitique(config)
    for ev in config.evenements:
        titre = str(ev["titre"]).strip()
        try:
            debut = _debut(ev["debut"])
            fin = debut + timedelta(minutes=int(ev.get("duree") or DUREE))
        except (TypeError, ValueError):
            rapport.anomalies.append(f"« {titre} » : heure illisible « {ev['debut']} » (écrire 2026-10-18 20:00)")
            continue
        resume = str(ev.get("resume") or "").strip()
        noms = ev["chaines"] if isinstance(ev["chaines"], list) else [ev["chaines"]]
        for nom in noms:
            chaine = _chaine(chaines, str(nom))
            if chaine is None:
                rapport.anomalies.append(f"« {titre} » : chaîne inconnue « {nom} » (nom de chaines.yaml)")
                continue
            invites, cites = filtre.presences(chaine, titre, resume, emission_blanche=True)
            rapport.retenues.append({
                "id": f"{PREFIXE}{debut:%Y%m%d%H%M}:{chaine.plateforme}:{normaliser(chaine.nom).replace(' ', '-')}",
                "titre": titre,
                "debut": debut.isoformat(timespec="seconds"),
                "fin": fin.isoformat(timespec="seconds"),
                "plateforme": chaine.plateforme,
                "chaine": chaine.nom,
                "categorie": str(ev.get("categorie") or filtre.categorie(titre, resume)),
                "invites": invites,
                "cites": cites,
                "resume": resume,
                "lien": list(chaine.direct),
                "statut": statut(debut, fin, maintenant),
                "filtre": "liste blanche",  # retenu d'office, comme une émission de la liste blanche
            })
    # Événement retiré du fichier : il passe en « annulé » (les autres sources n'y touchent pas).
    ids = {e["id"] for e in rapport.retenues}
    retires = [(i,) for i, d in connexion.execute(
        "SELECT id, debut FROM emissions WHERE id LIKE ? AND statut != 'annulé'", (PREFIXE + "%",))
        if i not in ids and datetime.fromisoformat(d) > maintenant]
    connexion.executemany("UPDATE emissions SET statut = 'annulé' WHERE id = ?", retires)
    rapport.annulees = len(retires)
    db.enregistrer_collecte(connexion, rapport.retenues, "evenement", set(), maintenant)
    return rapport
