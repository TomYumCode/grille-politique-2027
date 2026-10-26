"""Sujet du jour des émissions en cours, lu sur la page du direct de france.tv.

Le guide télé ne donne pour « C ce soir », « C dans l'air » ou « C à vous » qu'une
description générale, la même chaque soir. La page du direct de la chaîne
(https://www.france.tv/france-5/direct.html) donne, pour l'émission à l'antenne, son
sujet du jour, son résumé et ses heures exactes (données structurées schema.org).
France Télévisions ne les publie qu'au début de l'émission (vérifié le 23 octobre 2026) :
lue à chaque collecte, la page fait entrer dans la grille, pendant sa diffusion, une
émission dont le sujet du jour est politique. Les autres soirs, rien ne change.

Chaînes lues : lignes télévision de chaines.yaml dont le direct est une page france.tv.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import requests

from grille import db
from grille.config import Configuration
from grille.filtre import FiltrePolitique, normaliser
from grille.tv import EN_TETES, PARIS, statut

DELAI = 30
PAGE_DIRECT = re.compile(r"^https://www\.france\.tv/[\w-]+/direct\.html$")
ECART_MAX = timedelta(minutes=20)  # émission du guide déjà retenue : pas de doublon
_LDJSON = re.compile(r'(?s)<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>')
# Titre de la page : nom de l'émission (lien vers sa page) puis sujet du jour.
_TITRE = re.compile(r"(?s)<h2>\s*<a[^>]*>\s*<span[^>]*>(?P<emission>.*?)</span>\s*</a>\s*<span[^>]*>(?P<sujet>.*?)</span>\s*</h2>")
_SAISON = re.compile(r"^S\d+\s*-\s*")


@dataclass
class Rapport:
    pages_lues: int = 0
    illisibles: list[str] = field(default_factory=list)  # pages sans émission décrite (alerte si toutes)
    retenues: list[dict] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)
    interrompu: str = ""


def _texte(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def lire_page(texte: str) -> dict | None:
    """Émission à l'antenne : {emission, sujet, description, debut, fin}, ou None si la page est illisible."""
    video = None
    for bloc in _LDJSON.findall(texte):
        try:
            donnees = json.loads(bloc)
        except ValueError:
            continue
        for objet in donnees.get("@graph", [donnees]) if isinstance(donnees, dict) else []:
            if isinstance(objet, dict) and objet.get("@type") == "VideoObject" and objet.get("publication"):
                video = objet
    if not video:
        return None
    publication = video["publication"]
    try:
        debut = datetime.fromisoformat(publication["startDate"]).astimezone(PARIS)
        fin = datetime.fromisoformat(publication["endDate"]).astimezone(PARIS)
    except (KeyError, TypeError, ValueError):
        return None
    titre = _TITRE.search(texte)
    if titre:
        emission, sujet = _texte(titre["emission"]), _SAISON.sub("", _texte(titre["sujet"]))
    else:
        emission, sujet = _texte(video.get("name", "")), ""
    if not emission:
        return None
    return {"emission": emission, "sujet": sujet, "description": _texte(video.get("description", "")),
            "debut": debut, "fin": fin}


def _deja_en_grille(connexion, chaine: str, debut: datetime) -> bool:
    return any(e["chaine"] == chaine and e["plateforme"] == "tv" and not e["id"].startswith("direct:")
               and abs(datetime.fromisoformat(e["debut"]) - debut) <= ECART_MAX
               for e in db.lister(connexion, debut - ECART_MAX, debut + ECART_MAX))


def collecter(config: Configuration, session: requests.Session, connexion, maintenant: datetime) -> Rapport:
    rapport = Rapport()
    maintenant = maintenant.astimezone(PARIS)
    filtre = FiltrePolitique(config)
    chaines = [(c, next(d for d in c.direct if PAGE_DIRECT.match(d))) for c in config.chaines
               if c.plateforme == "tv" and any(PAGE_DIRECT.match(d) for d in c.direct)]
    for chaine, adresse in chaines:
        try:
            r = session.get(adresse, headers=EN_TETES, timeout=DELAI)
            r.raise_for_status()
        except requests.RequestException as e:
            rapport.anomalies.append(f"direct illisible : {chaine.nom} ({e})")
            continue
        en_cours = lire_page(r.text)
        if en_cours is None:
            # Pas d'alerte quotidienne pour une page sans émission décrite (décrochage régional…) ;
            # si aucune page n'est lisible, la collecte est notée en échec (format changé).
            rapport.illisibles.append(chaine.nom)
            continue
        rapport.pages_lues += 1
        if en_cours["fin"] <= maintenant or not en_cours["sujet"]:
            continue
        decision = filtre.decider(chaine, en_cours["emission"], en_cours["description"], sous_titre=en_cours["sujet"])
        if decision is None or _deja_en_grille(connexion, chaine.nom, en_cours["debut"]):
            continue
        rapport.retenues.append({
            "id": f"direct:{normaliser(chaine.nom).replace(' ', '-')}:{en_cours['debut']:%Y%m%d%H%M}",
            "titre": f"{en_cours['emission']} — {en_cours['sujet']}",
            "debut": en_cours["debut"].isoformat(timespec="seconds"),
            "fin": en_cours["fin"].isoformat(timespec="seconds"),
            "plateforme": "tv",
            "chaine": chaine.nom,
            "categorie": decision.categorie,
            "invites": decision.invites,
            "cites": decision.cites,
            "resume": en_cours["description"],
            "lien": list(chaine.direct),
            "statut": statut(en_cours["debut"], en_cours["fin"], maintenant),
            "filtre": decision.filtre,
            "motif": decision.motif,
        })
    if chaines and not rapport.pages_lues:
        rapport.interrompu = "aucune page du direct lisible : " + "; ".join(
            rapport.anomalies + [f"{n} : format de page inattendu" for n in rapport.illisibles])
    # Émission déjà commencée : jamais « annulée » par le guide (il n'annule que l'avenir).
    db.enregistrer_collecte(connexion, [{k: v for k, v in e.items() if k != "motif"} for e in rapport.retenues],
                            "tv", set(), maintenant)
    return rapport
