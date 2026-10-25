"""Collecteur télévision : guide XMLTV de xmltvfr.fr (TNT, aujourd'hui + 7 jours).

Le fichier ne donne pas d'identifiant d'émission : l'id est donc
« tv:<chaîne XMLTV>:<début> ». Un changement de titre met à jour la ligne ;
un changement d'heure crée une nouvelle ligne et annule l'ancienne.
"""

from __future__ import annotations

import gzip
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import BinaryIO, Iterator
from zoneinfo import ZoneInfo

import requests

from grille import FUSEAU, db
from grille.acces import XMLTV_TNT
from grille.config import Configuration
from grille.filtre import FiltrePolitique, normaliser

PARIS = ZoneInfo(FUSEAU)
JOURS_AFFICHES = 8  # aujourd'hui et les 7 jours suivants
DELAI = 120  # secondes, le fichier fait plusieurs mégaoctets
EN_TETES = {"User-Agent": "grille-politique-2027 (usage personnel)"}


@dataclass
class Programme:
    chaine_xmltv: str
    debut: datetime
    fin: datetime | None
    titre: str
    sous_titre: str = ""
    description: str = ""


@dataclass
class Rapport:
    lus: int = 0
    dans_l_horizon: int = 0
    masques: int = 0  # programmes de nuit ignorés (tv_heures_masquees)
    retenues: list[dict] = field(default_factory=list)
    annulees: int = 0
    chaines_absentes: list[str] = field(default_factory=list)
    douteux: int = 0  # nouveaux cas douteux (émissions écartées qui pourraient être politiques)


def lire_date(valeur: str) -> datetime:
    """« 20270315210000 +0100 » → datetime à l'heure de Paris. Sans décalage, l'heure est prise comme heure de Paris."""
    morceaux = valeur.strip().split()
    date = datetime.strptime(morceaux[0][:14], "%Y%m%d%H%M%S")
    if len(morceaux) > 1:
        date = date.replace(tzinfo=datetime.strptime(morceaux[1], "%z").tzinfo)
    else:
        date = date.replace(tzinfo=PARIS)
    return date.astimezone(PARIS)


def _texte(element: ET.Element, balise: str) -> str:
    """Texte de la première balise, en préférant la version française."""
    candidats = element.findall(balise)
    for c in candidats:
        if c.get("lang", "fr").startswith("fr") and c.text:
            return c.text.strip()
    return next((c.text.strip() for c in candidats if c.text), "")


def lire_xmltv(flux: BinaryIO, chaines_voulues: set[str] | None,
               icones: dict[str, str] | None = None) -> tuple[Iterator[Programme], set[str]]:
    """Lit le fichier au fil de l'eau (il est gros) ; renvoie les programmes et, à la fin, les chaînes vues.

    `chaines_voulues` à None : toutes les chaînes du guide. `icones`, s'il est fourni,
    reçoit l'adresse du logo de chaque chaîne voulue (balise <icon src> du guide).
    """
    chaines_vues: set[str] = set()

    def programmes() -> Iterator[Programme]:
        for _, element in ET.iterparse(flux, events=("end",)):
            if element.tag == "programme":
                chaine = element.get("channel", "")
                if chaines_voulues is None or chaine in chaines_voulues:
                    chaines_vues.add(chaine)
                    fin = element.get("stop")
                    yield Programme(
                        chaine,
                        lire_date(element.get("start", "")),
                        lire_date(fin) if fin else None,
                        _texte(element, "title"),
                        _texte(element, "sub-title"),
                        _texte(element, "desc"),
                    )
                element.clear()
            elif element.tag == "channel":
                icone = element.find("icon")
                identifiant = element.get("id", "")
                if icones is not None and icone is not None and icone.get("src") and (
                        chaines_voulues is None or identifiant in chaines_voulues):
                    icones[identifiant] = icone.get("src")
                element.clear()

    return programmes(), chaines_vues


def statut(debut: datetime, fin: datetime | None, maintenant: datetime) -> str:
    if debut <= maintenant and (fin is None or maintenant < fin):
        return "en direct"
    if fin is not None and fin <= maintenant:
        return "terminé"
    return "annoncé"


def telecharger(session: requests.Session, url: str = XMLTV_TNT) -> Path:
    """Télécharge le guide dans un fichier temporaire (gzip) et renvoie son chemin."""
    with session.get(url, stream=True, timeout=DELAI, headers=EN_TETES) as r:
        r.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".xml.gz", delete=False) as f:
            for bloc in r.iter_content(1 << 16):
                f.write(bloc)
    return Path(f.name)


def _ouvrir(chemin: Path) -> BinaryIO:
    with chemin.open("rb") as f:
        signature = f.read(2)
    return gzip.open(chemin, "rb") if signature == b"\x1f\x8b" else chemin.open("rb")


def collecter(config: Configuration, chemin: Path, connexion, maintenant: datetime) -> Rapport:
    """Lit le guide `chemin` (XML ou XML gzippé), filtre et écrit en base."""
    chaines_tv = {c.cle["xmltv_id"]: c for c in config.chaines if c.plateforme == "tv"}
    filtre = FiltrePolitique(config)
    maintenant = maintenant.astimezone(PARIS)
    fin_horizon = datetime.combine(maintenant.date() + timedelta(days=JOURS_AFFICHES), datetime.min.time(), PARIS)
    rapport = Rapport()
    non_retenus: dict[str, str] = {}  # id → titre normalisé des programmes écartés par le filtre

    with _ouvrir(chemin) as flux:
        icones: dict[str, str] = {}
        programmes, chaines_vues = lire_xmltv(flux, set(chaines_tv), icones)
        for p in programmes:
            rapport.lus += 1
            if p.debut >= fin_horizon or (p.fin or p.debut) <= maintenant:
                continue
            if config.tv_heures_masquees and config.tv_heures_masquees[0] <= p.debut.hour < config.tv_heures_masquees[1]:
                rapport.masques += 1
                continue
            rapport.dans_l_horizon += 1
            chaine = chaines_tv[p.chaine_xmltv]
            titre = f"{p.titre} — {p.sous_titre}" if p.sous_titre else p.titre
            decision = filtre.decider(chaine, p.titre, p.description, sous_titre=p.sous_titre)
            if decision is None:
                non_retenus[f"tv:{p.chaine_xmltv}:{p.debut.strftime('%Y%m%d%H%M')}"] = normaliser(p.titre)
                filtre.noter_douteux(f"tv:{p.chaine_xmltv}:{p.debut.strftime('%Y%m%d%H%M')}", "tv", chaine, titre,
                                     p.description, p.debut)
                continue
            rapport.retenues.append(
                {
                    "id": f"tv:{p.chaine_xmltv}:{p.debut.strftime('%Y%m%d%H%M')}",
                    "titre": titre,
                    "debut": p.debut.isoformat(timespec="seconds"),
                    "fin": p.fin.isoformat(timespec="seconds") if p.fin else None,
                    "plateforme": "tv",
                    "chaine": chaine.nom,
                    "categorie": decision.categorie,
                    "invites": decision.invites,
                    "cites": decision.cites,
                    "resume": p.description,
                    "lien": list(chaine.direct),
                    "statut": statut(p.debut, p.fin, maintenant),
                    "filtre": decision.filtre,
                    "motif": decision.motif,
                }
            )

    db.noter_logos(connexion, {chaines_tv[x].nom: url for x, url in icones.items()}, maintenant)
    rapport.douteux = db.noter_douteux(connexion, filtre.douteux, maintenant)
    rapport.chaines_absentes = sorted(c.nom for x, c in chaines_tv.items() if x not in chaines_vues)
    couvertes = {chaines_tv[x].nom for x in chaines_vues}
    a_ecrire = [{k: v for k, v in e.items() if k != "motif"} for e in rapport.retenues]
    # Même émission, même horaire, mais le guide a perdu sa description (« Objectif 2027 dimanche »
    # sur LCI, retenu le 21 octobre grâce à « élections présidentielles », annulé le lendemain) :
    # elle reste dans la grille. Un autre programme à la même heure, lui, l'annule.
    gardees = {i for i, titre in db.titres(connexion, set(non_retenus)).items()
               if normaliser(titre).startswith(non_retenus[i])}
    rapport.annulees = db.enregistrer_collecte(connexion, a_ecrire, "tv", couvertes, maintenant, gardees=gardees)
    return rapport


def chercher(config: Configuration, chemin: Path, texte: str, maintenant: datetime, limite: int = 60) -> list[dict]:
    """Programmes à venir dont le titre, le sous-titre ou la description contient `texte`.

    Toutes les chaînes du guide sont parcourues, configurées ou non, et chaque
    résultat dit ce que le filtre en ferait : utile pour régler politique.yaml.
    """
    from grille.filtre import normaliser

    chaines_tv = {c.cle["xmltv_id"]: c for c in config.chaines if c.plateforme == "tv"}
    filtre = FiltrePolitique(config)
    cherche = normaliser(texte)
    maintenant = maintenant.astimezone(PARIS)
    resultats = []
    with _ouvrir(chemin) as flux:
        programmes, _ = lire_xmltv(flux, None)
        for p in programmes:
            if (p.fin or p.debut) <= maintenant:
                continue
            if cherche not in normaliser(f"{p.titre} {p.sous_titre} {p.description}"):
                continue
            chaine = chaines_tv.get(p.chaine_xmltv)
            if chaine is None:
                verdict = f"chaîne non configurée ({p.chaine_xmltv})"
            elif config.tv_heures_masquees and config.tv_heures_masquees[0] <= p.debut.hour < config.tv_heures_masquees[1]:
                verdict = "masquée (programme de nuit)"
            else:
                decision = filtre.decider(chaine, p.titre, p.description, sous_titre=p.sous_titre)
                verdict = f"RETENUE : {decision.filtre}, {decision.motif}" if decision else "écartée : aucun mot-clé"
            resultats.append({"debut": p.debut, "chaine": chaine.nom if chaine else p.chaine_xmltv, "titre": p.titre,
                              "sous_titre": p.sous_titre, "description": p.description, "verdict": verdict})
            if len(resultats) >= limite:
                break
    return sorted(resultats, key=lambda r: r["debut"])
