"""Agendas publiés par les partis et les candidats (lignes « web » de chaines.yaml).

Deux sortes de rendez-vous :
- les passages dans les médias (« Andréa Kotarac sera l'invité de BFMTV le dimanche
  11 octobre à 17h ») : à l'affichage, l'invité rejoint l'émission de la chaîne à
  cette heure si elle est dans la grille ; sinon le rendez-vous apparaît seul ;
- les meetings et réunions publiques (« Réunion publique de François Asselineau »).

Seuls les rendez-vous qui citent un candidat ou une personnalité suivie sont gardés
(filtre politique habituel) : les réunions locales de militants ne le sont pas.

Chaque site a sa propre présentation : un lecteur par site, choisi d'après l'adresse.
Pages HTML sans API ; si une page change, aucun rendez-vous n'est lu et l'email du
matin le signale. Sites lisibles relevés le 11 octobre 2026 (docs/VERIFICATIONS.md).
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
from grille.filtre import FiltrePolitique, _contient, normaliser
from grille.tv import EN_TETES, JOURS_AFFICHES, PARIS, statut

DELAI = 30


@dataclass
class RendezVous:
    titre: str
    debut: datetime
    fin: datetime | None
    description: str
    lien: str = ""
    media: bool = False  # passage dans un média (télévision, radio)


@dataclass
class Rapport:
    agendas_lus: int = 0
    rendez_vous: int = 0
    retenues: list[dict] = field(default_factory=list)
    annulees: int = 0
    anomalies: list[str] = field(default_factory=list)
    interrompu: str = ""


class PageIllisible(Exception):
    pass


def _texte(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).replace("\xa0", " ").split())


def lire_rn(contenu: str, adresse: str, aujourdhui: date) -> list[RendezVous]:
    """rassemblementnational.fr/agenda : jour, mois, heure, titre, type (« Medias »…), phrase."""
    bloc = re.search(r"(?s)<h1>\s*Agenda\s*</h1>(.*)", contenu)
    if not bloc:
        raise PageIllisible("bloc « Agenda » introuvable")
    resultat = []
    for m in re.finditer(r'(?s)<h2>\s*(?P<jour>\d{1,2})\s*</h2>\s*<p[^>]*>\s*(?P<mois>[^<]+?)\s*</p>\s*'
                         r'<h3>\s*(?P<heure>[^<]*?)\s*</h3>.*?<div class="pt-2 grow">\s*<h3>(?P<titre>.*?)</h3>\s*'
                         r'<p[^>]*>(?P<type>.*?)</p>\s*<p[^>]*>(?P<texte>.*?)</p>', bloc.group(1)):
        quand = lire_date(f"{m['jour']} {m['mois']} {m['heure']}", aujourdhui)
        if quand is None:
            continue
        heure = time.fromisoformat(quand[1]) if quand[1] else time(0, 0)
        resultat.append(RendezVous(_texte(m["titre"]), datetime.combine(quand[0], heure, PARIS), None,
                                   _texte(m["texte"]), adresse, "media" in normaliser(m["type"])))
    return resultat


def lire_upr(contenu: str, adresse: str, aujourdhui: date) -> list[RendezVous]:
    """upr.fr/agenda : sections par mois (id="2026-10"), une carte AgendaEventCard par rendez-vous."""
    resultat = []
    for section in re.finditer(r'(?s)<section[^>]*data-agenda-month[^>]*id="(?P<an>\d{4})-(?P<mois>\d{2})"(?P<corps>.*?)'
                               r'(?=<section[^>]*data-agenda-month|$)', contenu):
        for carte in re.finditer(r'(?s)<article class="AgendaEventCard"[^>]*>.*?</article>', section["corps"]):
            c = carte.group(0)
            # Le site ajoute des attributs techniques (data-astro-cid-…) à chaque balise.
            jour = re.search(r'AgendaEventCard__day"[^>]*>\s*(\d{1,2})', c)
            titre = re.search(r"(?s)<h3[^>]*>(.*?)</h3>", c)
            if not (jour and titre):
                continue
            heures = re.findall(r"(\d{1,2}):(\d{2})", _texte(re.search(r'(?s)AgendaEventCard__meta.*?</div>', c).group(0))
                                if "AgendaEventCard__meta" in c else "")
            jour_j = date(int(section["an"]), int(section["mois"]), int(jour.group(1)))
            debut = datetime.combine(jour_j, time(*map(int, heures[0])) if heures else time(0, 0), PARIS)
            fin = datetime.combine(jour_j, time(*map(int, heures[1])), PARIS) if len(heures) > 1 else None
            description = re.search(r'(?s)AgendaEventCard__description"[^>]*>(.*?)</p>', c)
            lien = re.search(r'AgendaEventCard__cta"[^>]*?href="([^"]+)"', c)
            resultat.append(RendezVous(_texte(titre.group(1)), debut, fin, _texte(description.group(1) if description else ""),
                                       urljoin(adresse, lien.group(1)) if lien else adresse))
    if not resultat and "AgendaEventCard" not in contenu and "data-agenda-month" not in contenu:
        raise PageIllisible("aucune carte d'agenda")
    return resultat


LECTEURS: dict[str, Callable[[str, str, date], list[RendezVous]]] = {
    "rassemblementnational.fr": lire_rn,
    "upr.fr": lire_upr,
}


def lecteur(adresse: str) -> Callable[[str, str, date], list[RendezVous]] | None:
    hote = (urlparse(adresse).hostname or "").removeprefix("www.")
    return LECTEURS.get(hote)


def _media(rdv: RendezVous, config: Configuration) -> tuple[str, list[str]]:
    """Chaîne du passage média : nom de chaines.yaml si elle y figure (télévision et radio d'abord,
    pour le lien direct), sinon le nom écrit dans l'annonce (« Paris Première »)."""
    texte = normaliser(f"{rdv.description} {rdv.titre}")
    # Télévision et radio, puis les radios suivies seulement sur YouTube (RTL, Europe 1…) ;
    # pas les autres chaînes YouTube (« Le Monde » se trouve dans trop de phrases).
    candidates = sorted((c for c in config.chaines if c.plateforme in ("tv", "radio")
                         or (c.plateforme == "youtube" and normaliser(c.categorie).startswith("radio"))),
                        key=lambda c: (c.plateforme not in ("tv", "radio"), -len(c.nom)))
    for c in candidates:
        if _contient(texte, normaliser(c.nom)):
            directs = [d for x in config.chaines if x.nom == c.nom for d in x.direct]
            return c.nom, list(dict.fromkeys(directs))
    m = re.search(r"invitée?s? (?:de |d’|d')(?:la |l’|l')?(.+?) (?:le|ce|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\b",
                  rdv.description)
    if m:
        return m.group(1).strip(), []
    m = re.search(r"\bsur (.+)$", rdv.titre)
    return (m.group(1).strip() if m else rdv.titre), []


def collecter(config: Configuration, session: requests.Session, connexion, maintenant: datetime) -> Rapport:
    rapport = Rapport()
    filtre = FiltrePolitique(config)
    maintenant = maintenant.astimezone(PARIS)
    fin_horizon = datetime.combine(maintenant.date() + timedelta(days=JOURS_AFFICHES), datetime.min.time(), PARIS)
    couvertes: set[str] = set()
    agendas = [c for c in config.chaines if c.plateforme == "web"]
    for source in agendas:
        lire = lecteur(source.adresse)
        if lire is None:
            rapport.anomalies.append(f"agenda sans lecteur : {source.nom} ({source.adresse})")
            continue
        try:
            r = session.get(source.adresse, headers=EN_TETES, timeout=DELAI)
            r.raise_for_status()
            r.encoding = "utf-8"
            rendez_vous = lire(r.text, source.adresse, maintenant.date())
        except (requests.RequestException, PageIllisible) as e:
            rapport.anomalies.append(f"agenda illisible : {source.nom} ({e})")
            continue
        rapport.agendas_lus += 1
        couvertes.add(source.nom)
        for rdv in rendez_vous:
            if rdv.debut >= fin_horizon or (rdv.fin or rdv.debut + timedelta(hours=1)) <= maintenant:
                continue
            rapport.rendez_vous += 1
            decision = filtre.decider(source, rdv.titre, rdv.description)
            if decision is None:
                continue
            if rdv.media:
                chaine, liens = _media(rdv, config)
                categorie = "interview"
            else:
                chaine, liens = source.nom, [rdv.lien] if rdv.lien else []
                categorie = decision.categorie
            couvertes.add(chaine)
            rapport.retenues.append({
                "id": f"web:{urlparse(source.adresse).hostname}:{rdv.debut:%Y%m%d%H%M}:{normaliser(rdv.titre)[:60]}",
                "titre": rdv.titre,
                "debut": rdv.debut.isoformat(timespec="seconds"),
                "fin": rdv.fin.isoformat(timespec="seconds") if rdv.fin else None,
                "plateforme": "web",
                "chaine": chaine,
                "categorie": categorie,
                "invites": decision.invites,
                "lien": liens,
                "statut": statut(rdv.debut, rdv.fin, maintenant),
                "filtre": decision.filtre,
                "motif": decision.motif,
            })
    if agendas and not rapport.agendas_lus:
        rapport.interrompu = "aucun agenda lisible : " + "; ".join(rapport.anomalies)
        rapport.anomalies = []
    a_ecrire = [{k: v for k, v in e.items() if k != "motif"} for e in rapport.retenues]
    rapport.annulees = db.enregistrer_collecte(connexion, a_ecrire, "web", couvertes, maintenant)
    return rapport


def rattacher(emissions: list[dict]) -> list[dict]:
    """Passage média annoncé par un agenda (plateforme « web ») : s'il tombe pendant une émission
    de la même chaîne (télévision ou radio), l'invité rejoint cette émission et le rendez-vous
    n'est pas affiché à part."""
    diffusions = [e for e in emissions if e["plateforme"] in ("tv", "radio")]
    ajouts: dict[str, list[str]] = {}
    absorbes = set()
    for rdv in (e for e in emissions if e["plateforme"] == "web"):
        debut = datetime.fromisoformat(rdv["debut"])
        for e in diffusions:
            d = datetime.fromisoformat(e["debut"])
            f = datetime.fromisoformat(e["fin"]) if e["fin"] else d + timedelta(minutes=30)
            if e["chaine"] == rdv["chaine"] and d - timedelta(minutes=10) <= debut < f:
                ajouts.setdefault(e["id"], []).extend(rdv["invites"])
                absorbes.add(rdv["id"])
                break
    return [dict(e, invites=list(dict.fromkeys(e["invites"] + ajouts[e["id"]]))) if e["id"] in ajouts else e
            for e in emissions if e["id"] not in absorbes]
