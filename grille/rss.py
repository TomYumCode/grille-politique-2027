"""Mesure des flux RSS (presse, chaînes, sites médias) : annoncent-ils des passages médias
que la grille ne connaît pas encore ? (« Marine Tondelier invitée du 20 h de TF1 » : article
TF1info de 15 h 50 le 9 novembre 2026, invisible pour le guide et pour la recherche par Claude.)

Phase de mesure : rien n'est ajouté à la grille. À chaque collecte, les flux de config/rss.yaml
sont relus ; un article est une annonce probable quand il nomme une personne de politique.yaml,
une chaîne de télévision ou de radio de chaines.yaml et un mot de passage média (« invité »,
« sur le plateau », « au 20h »…). Il est noté une fois (table `rss_annonces`), avec l'heure de
publication, l'heure où la collecte l'a vu et si la grille connaissait déjà ce passage
(personne présente dans une émission de la même chaîne, de la veille au lendemain). L'email
du matin en fait le compte, pour décider ensuite de brancher ou non ces flux.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import requests

from grille import affichage, db
from grille.config import Configuration
from grille.filtre import FiltrePolitique, normaliser
from grille.tv import PARIS

DELAI = 20
EN_TETES = {"User-Agent": "Mozilla/5.0 (compatible; grille-politique-2027; mesure de flux RSS)"}
RECENT = timedelta(hours=36)  # articles plus anciens ignorés
# Mots d'un passage média (texte normalisé, sans accents).
_PASSAGE = re.compile(
    r"\b(invite|invitee|invites|invitees|sera l invite|plateau|face a|interview|interviewe|interviewee|entretien|"
    r"au 20h|au 20 heures|au 13h|au 13 heures|journal de 20|journal de 13|ce soir sur|ce matin sur|demain sur|"
    r"dans l emission|matinale|grand oral|grand jury|questions politiques|repondra|repond aux questions|"
    r"sur le plateau de)\b")


@dataclass
class Rapport:
    flux_lus: int = 0
    articles: int = 0
    nouvelles: list[dict] = field(default_factory=list)  # annonces probables vues pour la première fois
    anomalies: list[str] = field(default_factory=list)


def _texte(fragment: str | None) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).split())


def _date(valeur: str | None) -> datetime | None:
    if not valeur:
        return None
    valeur = valeur.strip()
    try:
        d = parsedate_to_datetime(valeur)  # RSS : « Mon, 09 Nov 2026 15:50:00 +0100 »
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(valeur.replace("Z", "+00:00"))  # Atom : ISO 8601
        except ValueError:
            return None
    return (d if d.tzinfo else d.replace(tzinfo=PARIS)).astimezone(PARIS)


def lire_flux(contenu: bytes) -> list[dict]:
    """Articles d'un flux RSS 2.0 ou Atom : titre, résumé, lien, identifiant, date de publication."""
    racine = ET.fromstring(contenu)
    articles = []
    for noeud in racine.iter():
        if noeud.tag.split("}")[-1] not in ("item", "entry"):
            continue
        champs: dict[str, str] = {}
        for c in noeud:
            nom = c.tag.split("}")[-1]
            if nom == "link" and c.get("href"):
                champs.setdefault("link", c.get("href"))
            elif c.text and nom not in champs:
                champs[nom] = c.text
        lien = (champs.get("link") or "").strip()
        articles.append({
            "titre": _texte(champs.get("title")),
            "resume": _texte(champs.get("description") or champs.get("summary") or champs.get("content")),
            "lien": lien,
            "id": (champs.get("guid") or champs.get("id") or lien).strip(),
            "publie": _date(champs.get("pubDate") or champs.get("published") or champs.get("updated")
                            or champs.get("date")),
        })
    return articles


def _chaines(config: Configuration) -> list[tuple[str, str]]:
    """(nom affiché, forme normalisée) des chaînes de télévision et de radio, sans doublon."""
    vues: dict[str, str] = {}
    for c in config.chaines:
        if c.plateforme in ("tv", "radio"):
            nom = re.sub(r"\s*\((tv|radio)\)$", "", c.nom)
            for forme in {nom, *nom.split(" / ")}:
                vues.setdefault(normaliser(forme), forme)
    return [(nom, forme) for forme, nom in vues.items() if forme]


def annonce(article: dict, filtre: FiltrePolitique, chaines: list[tuple[str, str]]) -> dict | None:
    """Personnes et chaînes d'une annonce probable de passage média, ou None."""
    texte = f"{article['titre']}. {article['resume']}"
    texte_n = normaliser(texte)
    if not _PASSAGE.search(texte_n):
        return None
    personnes = filtre.personnes_nommees(texte)
    nommees = [nom for nom, forme in chaines if f" {forme} " in f" {texte_n} "]
    if not personnes or not nommees:
        return None
    return {"personnes": personnes, "chaines": nommees}


def deja_en_grille(emissions: list[dict], personnes: list[str], chaines: list[str]) -> bool:
    """La grille montre déjà une de ces personnes dans une émission d'une de ces chaînes."""
    chaines_n = {normaliser(c) for c in chaines}
    for e in emissions:
        noms = {normaliser(s["chaine"]) for s in e.get("sources") or []} | {normaliser(e["chaine"])}
        noms |= {n for nom in list(noms) for n in nom.split(" / ")}
        if noms & chaines_n and set(e["invites"]) & set(personnes):
            return True
    return False


def collecter(config: Configuration, session: requests.Session, connexion, maintenant: datetime) -> Rapport:
    rapport = Rapport()
    maintenant = maintenant.astimezone(PARIS)
    filtre = FiltrePolitique(config)
    chaines = _chaines(config)
    grille = affichage.emissions(connexion, maintenant - timedelta(days=1), maintenant + timedelta(days=2))
    connues = db.rss_ids(connexion)
    for flux in config.rss:
        try:
            r = session.get(flux["adresse"], headers=EN_TETES, timeout=DELAI)
            r.raise_for_status()
            articles = lire_flux(r.content)
        except (requests.RequestException, ET.ParseError) as e:
            rapport.anomalies.append(f"flux illisible : {flux['nom']} ({type(e).__name__})")
            continue
        rapport.flux_lus += 1
        for a in articles:
            if not a["id"] or a["id"] in connues or (a["publie"] and a["publie"] < maintenant - RECENT):
                continue
            rapport.articles += 1
            trouve = annonce(a, filtre, chaines)
            if trouve is None:
                continue
            connues.add(a["id"])
            rapport.nouvelles.append({
                "id": a["id"], "flux": flux["nom"], "titre": a["titre"], "lien": a["lien"],
                "publie": a["publie"].isoformat(timespec="seconds") if a["publie"] else "",
                "vu_le": maintenant.isoformat(timespec="seconds"),
                "personnes": trouve["personnes"], "chaines": trouve["chaines"],
                "deja_en_grille": deja_en_grille(grille, trouve["personnes"], trouve["chaines"]),
            })
    db.noter_rss(connexion, rapport.nouvelles, maintenant)
    return rapport
