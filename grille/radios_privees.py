"""Radios privées : grilles publiées sur les sites (RTL, Europe 1, Sud Radio).

Lignes « radio » de chaines.yaml dont l'adresse est une page web (les codes de station
Radio France passent par l'API, grille/radio.py). Un lecteur par site, choisi d'après
l'adresse. Chaque grille donne des émissions et, dedans, des chroniques à l'heure près
(« 08h10 - 08h27 La Grande interview Europe 1 - CNews ») : les deux sont filtrées.

Les résumés des sites (« Au programme : Glucksmann remporte la primaire… ») citent
l'actualité : lus tels quels, ils feraient entrer chaque journal. Ils ne servent donc
au filtre que pour les créneaux d'invités (titre avec « invité », « interview »…).

Pages HTML sans API, relevées le 12 octobre 2026 (docs/VERIFICATIONS.md) ; si une page
change, la radio est signalée dans l'email du matin.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Callable
from urllib.parse import urljoin, urlparse

import requests

from grille import db
from grille.annonces import lire_date
from grille.config import Chaine, Configuration
from grille.filtre import FiltrePolitique, normaliser
from grille.tv import EN_TETES, JOURS_AFFICHES, PARIS, statut

DELAI = 30
JOURS_SEMAINE = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
# Créneaux d'invités : leur résumé peut nommer l'invité, on le donne au filtre.
_CRENEAU_INVITE = re.compile(r"\b(invit\w*|interview\w*|entretien\w*|face a face|debat\w*|grand jury|questions? politiques?)\b")


@dataclass
class Programme:
    titre: str
    debut: datetime
    fin: datetime | None
    description: str = ""
    lien: str = ""


@dataclass
class Rapport:
    radios_lues: int = 0
    pages_lues: int = 0
    programmes: int = 0
    masques: int = 0
    retenues: list[dict] = field(default_factory=list)
    annulees: int = 0
    douteux: int = 0
    anomalies: list[str] = field(default_factory=list)
    interrompu: str = ""


class PageIllisible(Exception):
    pass


def _texte(fragment: str | None) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).replace("\xa0", " ").split())


def _heure(texte: str) -> time | None:
    m = re.search(r"(\d{1,2})\s*[hH:]\s*(\d{2})", texte or "")
    return time(int(m.group(1)) % 24, int(m.group(2))) if m else None


class _Horloge:
    """Transforme les heures d'une page en dates : une grille de jour continue après minuit
    (« 00h30 - 01h00 » est le lendemain)."""

    def __init__(self, jour: date):
        self.jour, self.precedente = jour, None

    def __call__(self, h: time | None) -> datetime | None:
        if h is None:
            return None
        quand = datetime.combine(self.jour, h, PARIS)
        if self.precedente and quand < self.precedente - timedelta(hours=6):
            self.jour += timedelta(days=1)
            quand += timedelta(days=1)
        self.precedente = quand
        return quand


def _chroniques_avec_fin(chroniques: list[Programme], fin_emission: datetime | None) -> list[Programme]:
    """Une chronique sans heure de fin finit à la suivante (ou avec l'émission)."""
    chroniques.sort(key=lambda p: p.debut)
    for i, p in enumerate(chroniques):
        if p.fin is None:
            p.fin = chroniques[i + 1].debut if i + 1 < len(chroniques) else fin_emission
    return chroniques


def lire_rtl(contenu: str, adresse: str, jour: date) -> list[Programme]:
    """rtl.fr/grille/JJ-MM-AAAA : cartes « programme-card » (heure « 07h00 - 09h00 », titre, animateurs,
    description) et leurs chroniques (« 07h40 », titre, animateurs, description)."""
    cartes = re.split(r'(?=<div class="programme-card[ "])', contenu)[1:]
    if not cartes:
        raise PageIllisible("aucune carte de programme")
    horloge, resultat = _Horloge(jour), []
    for c in cartes:
        horaires = re.search(r'programme-card__time[^>]*>(.*?)</', c, re.S)
        titre = re.search(r'programme-card__title[^>]*>(.*?)</', c, re.S)
        if not (horaires and titre):
            continue
        bornes = _texte(horaires.group(1)).split("-")
        debut = horloge(_heure(bornes[0]))
        if debut is None:
            continue
        fin_h = _heure(bornes[1]) if len(bornes) > 1 else None
        fin = datetime.combine(debut.date(), fin_h, PARIS) if fin_h else None
        if fin and fin <= debut:
            fin += timedelta(days=1)
        lien = re.search(r'<a href="([^"]+)"', c)
        description = re.search(r'programme-card__description[^>]*>(.*?)</p>', c, re.S)
        resultat.append(Programme(_texte(titre.group(1)), debut, fin, _texte(description.group(1) if description else ""),
                                  urljoin(adresse, lien.group(1)) if lien else adresse))
        chroniques = []
        for li in re.findall(r'(?s)<li class="programme-card__chronique".*?</li>', c):
            h = re.search(r'programme-card__chronique-time[^>]*>(.*?)</p>', li, re.S)
            t = re.search(r'programme-card__chronique-title[^>]*>(.*?)</', li, re.S)
            if not (h and t):
                continue
            h_debut = _heure(_texte(h.group(1)))
            if h_debut is None:
                continue
            d = datetime.combine(debut.date(), h_debut, PARIS)
            if d < debut:
                d += timedelta(days=1)
            desc = re.search(r'programme-card__chronique-description[^>]*>(.*?)</p>', li, re.S)
            l = re.search(r'<a href="([^"]+)"', li)
            chroniques.append(Programme(_texte(t.group(1)), d, None, _texte(desc.group(1) if desc else ""),
                                        urljoin(adresse, l.group(1)) if l else adresse))
        resultat += _chroniques_avec_fin(chroniques, fin)
    return resultat


def lire_europe1(contenu: str, adresse: str, aujourdhui: date) -> list[Programme]:
    """europe1.fr/grille-des-programmes : grille type de la semaine, un panneau par jour
    (id="panel-lundi"…), émissions (« horaires-item-programme ») et chroniques
    (« horaires-item-chronique »). Pas de date : chaque jour est placé sur sa prochaine occurrence."""
    panneaux = list(re.finditer(r'<section\s+id="panel-(\w+)"', contenu))
    if not panneaux:
        raise PageIllisible("aucun panneau de jour")
    resultat = []
    for i, p in enumerate(panneaux):
        nom = p.group(1).lower()
        if nom not in JOURS_SEMAINE:
            continue
        jour = aujourdhui + timedelta(days=(JOURS_SEMAINE.index(nom) - aujourdhui.weekday()) % 7)
        bloc = contenu[p.end(): panneaux[i + 1].start() if i + 1 < len(panneaux) else len(contenu)]
        horloge = _Horloge(jour)
        # Émissions et chroniques dans l'ordre de la page : l'émission précède ses chroniques.
        for m in re.finditer(r'(?s)class="horaires-item-(programme|chronique)">(.*?)</div>(.*?)'
                             r'class="title-item-\1">(.*?)</(?:p|div)>', bloc):
            bornes = _texte(m.group(2)).split("-")
            debut = horloge(_heure(bornes[0]))
            if debut is None:
                continue
            fin_h = _heure(bornes[1]) if len(bornes) > 1 else None
            fin = datetime.combine(debut.date(), fin_h, PARIS) if fin_h else None
            if fin and fin <= debut:
                fin += timedelta(days=1)
            avant = bloc[max(0, m.start() - 600): m.start()]
            lien = re.findall(r'<a href="([^"]+)"', avant + m.group(3))
            resultat.append(Programme(_texte(m.group(4)), debut, fin, "",
                                      urljoin(adresse, lien[-1]) if lien else adresse))
    return resultat


def lire_sudradio(contenu: str, adresse: str, aujourdhui: date) -> list[Programme]:
    """sudradio.fr/programmes (?week=1 : semaine suivante) : un panneau par jour titré
    « lundi 12 octobre », émissions (« program-start », nom, « Au programme ») et chroniques
    (« sud_deb_chronique », titre, description)."""
    jours = list(re.finditer(r'(?s)<h2 class="sud_planning_titre_jour">(.*?)</h2>', contenu))
    if not jours:
        # La semaine suivante peut être encore vide ; sans trace de la grille, la page a changé.
        if "sud_planning" in contenu:
            return []
        raise PageIllisible("aucun jour dans la grille")
    resultat = []
    for i, j in enumerate(jours):
        quand = lire_date(_texte(j.group(1)), aujourdhui)
        if quand is None:
            continue
        bloc = contenu[j.end(): jours[i + 1].start() if i + 1 < len(jours) else len(contenu)]
        horloge = _Horloge(quand[0])
        for ligne in re.split(r'(?=<li class="sud_planning_ligne)', bloc)[1:]:
            debut = horloge(_heure(_texte((re.search(r'(?s)program-start">(.*?)</span>', ligne) or [None, ""])[1])))
            nom = re.search(r'(?s)sud_planning_program_name">(.*?)</h3>', ligne)
            if debut is None or not nom:
                continue
            fin_h = _heure(_texte((re.search(r'(?s)program-end">(.*?)</span>', ligne) or [None, ""])[1]))
            fin = datetime.combine(debut.date(), fin_h, PARIS) if fin_h else None
            if fin and fin <= debut:
                fin += timedelta(days=1)
            extrait = re.search(r'(?s)sud_planning_extrait">(.*?)</blockquote>', ligne)
            lien_emission = re.search(r'href="(https://www\.sudradio\.fr/emission/[^"]+)"', ligne)
            resultat.append(Programme(_texte(nom.group(1)), debut, fin,
                                      _texte(extrait.group(1) if extrait else "").removeprefix("Au programme :").strip(),
                                      lien_emission.group(1) if lien_emission else adresse))
            chroniques = []
            for art in re.findall(r'(?s)<article[^>]*class="sud_podcast_chronique".*?</article>', ligne):
                heures = re.findall(r"(\d{1,2})\s*H\s*(\d{2})", _texte(
                    (re.search(r'(?s)sud_podcast_chronique_hour">(.*?)</div>', art) or [None, ""])[1]), re.I)
                titre = re.search(r'(?s)sud_podcast_chronique_link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', art)
                if not heures or not titre:
                    continue
                d = datetime.combine(debut.date(), time(int(heures[0][0]) % 24, int(heures[0][1])), PARIS)
                if d < debut:
                    d += timedelta(days=1)
                f = datetime.combine(d.date(), time(int(heures[1][0]) % 24, int(heures[1][1])), PARIS) if len(heures) > 1 else None
                desc = re.search(r'(?s)sud_podcast_chronique_description">(.*?)</p>', art)
                chroniques.append(Programme(_texte(titre.group(2)), d, f, _texte(desc.group(1) if desc else ""),
                                            titre.group(1)))
            resultat += _chroniques_avec_fin(chroniques, fin)
    return resultat


def pages_rtl(adresse: str, maintenant: datetime) -> list[tuple[str, date]]:
    """Une page par jour : aujourd'hui et demain à chaque collecte, plus un des jours suivants
    à tour de rôle (chaque jour est relu au moins toutes les 6 heures ; pages lourdes)."""
    racine = adresse.rstrip("/")
    jour = maintenant.date()
    jours = [jour, jour + timedelta(days=1), jour + timedelta(days=2 + maintenant.hour % (JOURS_AFFICHES - 2))]
    return [(f"{racine}/{j:%d-%m-%Y}", j) for j in dict.fromkeys(jours)]


def pages_semaine(adresse: str, maintenant: datetime) -> list[tuple[str, date]]:
    return [(adresse, maintenant.date())]


def pages_sudradio(adresse: str, maintenant: datetime) -> list[tuple[str, date]]:
    return [(adresse, maintenant.date()), (f"{adresse}?week=1", maintenant.date())]


@dataclass
class Lecteur:
    lire: Callable[[str, str, date], list[Programme]]
    pages: Callable[[str, datetime], list[tuple[str, date]]]
    # Jours couverts par une page (pour n'annuler que ce qui a été relu).
    jours_couverts: Callable[[date], list[date]]


LECTEURS = {
    "rtl.fr": Lecteur(lire_rtl, pages_rtl, lambda j: [j]),
    "europe1.fr": Lecteur(lire_europe1, pages_semaine, lambda j: [j + timedelta(days=i) for i in range(7)]),
    "sudradio.fr": Lecteur(lire_sudradio, pages_sudradio, lambda j: []),  # dates lues dans la page
}


def lecteur(adresse: str) -> Lecteur | None:
    return LECTEURS.get((urlparse(adresse).hostname or "").removeprefix("www."))


def _description_pour_le_filtre(titre: str, description: str) -> str:
    return description if _CRENEAU_INVITE.search(normaliser(titre)) else ""


def collecter(config: Configuration, session: requests.Session, connexion, maintenant: datetime) -> Rapport:
    rapport = Rapport()
    filtre = FiltrePolitique(config)
    maintenant = maintenant.astimezone(PARIS)
    fin_horizon = datetime.combine(maintenant.date() + timedelta(days=JOURS_AFFICHES), datetime.min.time(), PARIS)
    radios = [c for c in config.chaines if c.plateforme == "radio" and "url" in c.cle]
    for chaine in radios:
        lect = lecteur(chaine.adresse)
        if lect is None:
            rapport.anomalies.append(f"radio sans lecteur : {chaine.nom} ({chaine.adresse})")
            continue
        programmes, jours = [], set()
        for url, jour in lect.pages(chaine.adresse, maintenant):
            try:
                r = session.get(url, headers=EN_TETES, timeout=DELAI)
                r.raise_for_status()
                r.encoding = "utf-8"
                lus = lect.lire(r.text, url, jour)
            except (requests.RequestException, PageIllisible) as e:
                rapport.anomalies.append(f"grille illisible : {chaine.nom} ({e})")
                continue
            rapport.pages_lues += 1
            programmes += lus
            jours.update(lect.jours_couverts(jour) or {p.debut.date() for p in lus})
        if not jours:
            continue
        rapport.radios_lues += 1
        retenues = []
        for p in programmes:
            if p.debut >= fin_horizon or (p.fin or p.debut + timedelta(minutes=30)) <= maintenant:
                continue
            if config.tv_heures_masquees and config.tv_heures_masquees[0] <= p.debut.hour < config.tv_heures_masquees[1]:
                rapport.masques += 1
                continue
            rapport.programmes += 1
            id_ = f"radio:{urlparse(chaine.adresse).hostname}:{p.debut:%Y%m%d%H%M}:{normaliser(p.titre)[:40]}"
            description = _description_pour_le_filtre(p.titre, p.description)
            decision = filtre.decider(chaine, p.titre, description)
            if decision is None:
                filtre.noter_douteux(id_, "radio", chaine, p.titre, description, p.debut)
                continue
            retenues.append({
                "id": id_, "titre": p.titre,
                "debut": p.debut.isoformat(timespec="seconds"),
                "fin": p.fin.isoformat(timespec="seconds") if p.fin else None,
                "plateforme": "radio", "chaine": chaine.nom,
                "categorie": decision.categorie, "invites": decision.invites,
                "lien": [p.lien] + [d for d in chaine.direct if d != p.lien],
                "statut": statut(p.debut, p.fin, maintenant),
                "filtre": decision.filtre, "motif": decision.motif,
            })
        a_ecrire = [{k: v for k, v in e.items() if k != "motif"} for e in retenues]
        rapport.annulees += db.enregistrer_collecte(connexion, a_ecrire, "radio", {chaine.nom}, maintenant, jours)
        rapport.retenues += retenues
    rapport.douteux = db.noter_douteux(connexion, filtre.douteux, maintenant)
    if radios and not rapport.radios_lues:
        rapport.interrompu = "aucune grille de radio privée lisible : " + "; ".join(rapport.anomalies)
        rapport.anomalies = []
    return rapport
