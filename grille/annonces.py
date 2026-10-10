"""Invités annoncés : communiqués de presse de France Télévisions (francetvpro.fr).

Les communiqués annoncent souvent l'invité d'une émission avant sa diffusion, quand
le guide télévision ne donne que le titre (« FRANC-JEU / Roland Lescure / Invité de
Benjamin Duhamel — Dimanche 11 octobre à 13h20 sur France 2 »). Le collecteur lit
les premières pages de la liste des communiqués et garde ceux qui portent une date
à venir. À l'affichage, une annonce complète les invités de l'émission du même jour,
à la même heure (à 30 minutes près) et au titre concordant.

Page HTML sans API : si sa structure change, aucune annonce n'est lue et l'email du
matin le signale (« aucune annonce lue »).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import requests

from grille import db
from grille.acces import FRANCETVPRO
from grille.config import Configuration
from grille.filtre import FiltrePolitique, normaliser
from grille.fusion import MOTS_VIDES
from grille.tv import EN_TETES, PARIS

DELAI = 30
PAGES = 4  # une douzaine de communiqués par page, les plus récents d'abord
ECART_MAX = timedelta(minutes=30)
MOIS = {m: i for i, m in enumerate(["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout",
                                     "septembre", "octobre", "novembre", "decembre"], start=1)}

_CARTE = re.compile(r'(?s)<h4 class="card__title"><a href="(?P<lien>[^"]+)">\s*<div>(?P<titre>.*?)</div>.*?</h4>'
                    r'(?:\s*<div class="card__date"><div>(?P<date>.*?)</div></div>)?'
                    r'(?:\s*<div class="card__text">\s*<div>(?P<texte>.*?)</div>)?')
_DATE = re.compile(r"(?i)\b(?P<jour>\d{1,2})(?:er)?\s+(?P<mois>[a-zéû]+)(?:\s+(?P<annee>20\d\d))?"
                   r"(?:.*?\b(?P<h>\d{1,2})\s*(?:h|:|\.)\s*(?P<m>\d{2})?)?")
# Nom propre : deux à quatre mots à majuscule, particules admises (« Dominique de Villepin »).
# Un mot tout en majuscules (« FRANC-JEU ») n'est pas un nom.
_MAJ = r"[A-ZÉÈÊÀÂÎÔÛÇ][a-zà-ÿœ’']+(?:-[A-ZÉÈÊÀÂÎÔÛÇ]?[a-zà-ÿœ’']+)*"
_NOM = rf"{_MAJ}(?:\s+(?:de\s+|du\s+|d’|d'|le\s+|la\s+)?{_MAJ}){{1,3}}"
_RECOIT = re.compile(rf"reçoi(?:t|vent)\s+(?P<noms>{_NOM}(?:\s*(?:,|et)\s*{_NOM})*)")
_INVITE_DE = re.compile(rf"(?P<noms>{_NOM}(?:\s*(?:,|et)\s*{_NOM})*)\s*,?\s+invitée?s?\s+(?:de|d’|d')")


@dataclass
class Annonce:
    id: str
    titre: str
    jour: str  # AAAA-MM-JJ
    heure: str  # HH:MM, ou "" quand le communiqué ne la donne pas
    invites: list[str]
    url: str


@dataclass
class Rapport:
    pages_lues: int = 0
    cartes: int = 0
    retenues: list[Annonce] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)
    interrompu: str = ""


def _texte(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).replace("\xa0", " ").split())


def lire_date(texte: str, aujourdhui: date) -> tuple[date, str] | None:
    """« Dimanche 11 octobre à 13h20 sur France 2 » → (2026-10-11, "13:20"). Sans année,
    la date la plus proche d'aujourd'hui (au plus un mois en arrière)."""
    # « Vendredi 9 et samedi 10 octobre » : la première forme « jour mois » valable.
    m = next((m for m in _DATE.finditer(texte) if normaliser(m["mois"]) in MOIS), None)
    if m is None:
        return None
    mois, jour = MOIS[normaliser(m["mois"])], int(m["jour"])
    try:
        if m["annee"]:
            quand = date(int(m["annee"]), mois, jour)
        else:
            quand = date(aujourdhui.year, mois, jour)
            if quand < aujourdhui - timedelta(days=31):
                quand = date(aujourdhui.year + 1, mois, jour)
    except ValueError:
        return None
    heure = f"{int(m['h']):02d}:{int(m['m'] or 0):02d}" if m["h"] and int(m["h"]) < 24 else ""
    return quand, heure


def _noms(groupe: str) -> list[str]:
    return [n.strip() for n in re.split(r"\s*,\s*|\s+et\s+", groupe) if re.fullmatch(_NOM, n.strip())]


def invites(parties: list[str], resume: str, filtre: FiltrePolitique) -> list[str]:
    """Invités nommés dans le titre du communiqué ou son résumé."""
    trouves: list[str] = []
    # Titre en plusieurs lignes : « FRANC-JEU / Roland Lescure / Invité de Benjamin Duhamel ».
    for partie in parties[1:]:
        if re.match(r"(?i)\s*(invit|présent|anim|avec\b|en direct|à suivre)", partie):
            continue
        trouves += _noms(partie)
    # « … reçoit Yannick Jadot », « Roland Lescure, invité de … » : titre d'une seule ligne et résumé.
    for texte in ([parties[0]] if len(parties) == 1 else []) + [resume]:
        for motif in (_RECOIT, _INVITE_DE):
            for m in motif.finditer(texte):
                trouves += _noms(m["noms"])
    # Candidats et personnalités suivis, cités n'importe où (« débat avec Marion Maréchal »).
    trouves += filtre.invites(" ".join(parties) + "\n" + resume)
    return list(dict.fromkeys(trouves))


def lire_page(contenu: str, aujourdhui: date, filtre: FiltrePolitique) -> tuple[int, list[Annonce]]:
    """Renvoie le nombre de cartes lues et les annonces datées d'aujourd'hui ou plus tard."""
    cartes, annonces = 0, []
    for m in _CARTE.finditer(contenu):
        cartes += 1
        parties = [p for p in (_texte(x) for x in re.split(r"(?i)<br\s*/?>", m["titre"])) if p]
        quand = lire_date(_texte(m["date"]), aujourdhui) if m["date"] else None
        if not parties or quand is None or quand[0] < aujourdhui:
            continue
        noms = invites(parties, _texte(m["texte"]), filtre)
        if not noms:
            continue
        lien = m["lien"] if m["lien"].startswith("http") else FRANCETVPRO.split("/contenu-de-presse")[0] + m["lien"]
        annonces.append(Annonce(m["lien"].rstrip("/").rsplit("/", 1)[-1], " — ".join(parties),
                                quand[0].isoformat(), quand[1], noms, lien))
    return cartes, annonces


def collecter(config: Configuration, session: requests.Session, connexion, maintenant: datetime) -> Rapport:
    rapport = Rapport()
    filtre = FiltrePolitique(config)
    aujourdhui = maintenant.astimezone(PARIS).date()
    for page in range(PAGES):
        try:
            r = session.get(FRANCETVPRO, params={"page": page}, headers=EN_TETES, timeout=DELAI)
            r.raise_for_status()
        except requests.RequestException as e:
            rapport.anomalies.append(f"page {page + 1} des communiqués illisible ({e})")
            continue
        rapport.pages_lues += 1
        cartes, annonces = lire_page(r.text, aujourdhui, filtre)
        rapport.cartes += cartes
        rapport.retenues += annonces
    if not rapport.pages_lues:
        rapport.interrompu = "francetvpro.fr inaccessible : " + "; ".join(rapport.anomalies)
        rapport.anomalies = []
    elif not rapport.cartes:
        rapport.interrompu = "aucun communiqué reconnu : la page a sans doute changé de structure"
    db.noter_annonces(connexion, [vars(a) for a in rapport.retenues], maintenant)
    return rapport


def _mots(titre: str) -> set[str]:
    return {m for m in normaliser(titre).split() if m not in MOTS_VIDES}


def _concorde(emission: dict, annonce: dict) -> bool:
    debut = datetime.fromisoformat(emission["debut"])
    if debut.date().isoformat() != annonce["jour"]:
        return False
    if annonce["heure"]:
        h, m = map(int, annonce["heure"].split(":"))
        if abs(debut - debut.replace(hour=h, minute=m, second=0)) > ECART_MAX:
            return False
    # Titre principal de l'émission (avant le sous-titre du guide), tous ses mots dans l'annonce.
    mots = _mots(emission["titre"].split(" — ")[0])
    return bool(mots) and (len(mots) >= 2 or bool(annonce["heure"])) and mots <= _mots(annonce["titre"])


def enrichir(emissions: list[dict], annonces: list[dict]) -> list[dict]:
    """Ajoute aux émissions les invités annoncés par communiqué (sans toucher à la base)."""
    resultat = []
    for e in emissions:
        noms = [n for a in annonces if _concorde(e, a) for n in a["invites"]]
        if noms:
            e = dict(e, invites=list(dict.fromkeys(e["invites"] + noms)))
        resultat.append(e)
    return resultat
