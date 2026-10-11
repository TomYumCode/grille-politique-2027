"""Collecteur radio : grille des programmes de l'API ouverte de Radio France.

Une requête GraphQL « grid » par station (France Inter, franceinfo, France Culture…)
couvre aujourd'hui et les 7 jours suivants : 24 collectes × 3 stations = 72 requêtes
par jour. La clé passe dans l'adresse (`?x-token=…`) : ne jamais afficher l'adresse
complète, les journaux de GitHub sont publics.

Forme de la requête reprise d'une intégration publique (voir docs/VERIFICATIONS.md) ;
la documentation officielle n'était pas joignable pendant le développement. Le champ
`show` (nom de l'émission) n'y figurait pas : s'il est refusé, le collecteur refait
la requête sans lui et le signale.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import requests

from grille import db
from grille.acces import RADIOFRANCE_API
from grille.config import Configuration
from grille.filtre import FiltrePolitique
from grille.tv import JOURS_AFFICHES, PARIS, statut

DELAI = 30

_ETAPES = """
    ... on DiffusionStep {{ id start end diffusion {{ id title standFirst url{show} }} }}
    ... on BlankStep {{ id title start end }}
"""
REQUETE = "{{ grid(start: {debut}, end: {fin}, station: {station}) {{" + _ETAPES + "}} }}"
AVEC_EMISSION = " show { title }"


@dataclass
class Rapport:
    stations_lues: int = 0
    programmes: int = 0
    masques: int = 0
    retenues: list[dict] = field(default_factory=list)
    annulees: int = 0
    anomalies: list[str] = field(default_factory=list)
    interrompu: str = ""


SANS_CLE = "secret RADIOFRANCE_API_KEY absent"


class ErreurRadioFrance(Exception):
    pass


def requete(station: str, debut: datetime, fin: datetime, avec_emission: bool = True) -> str:
    return REQUETE.format(debut=int(debut.timestamp()), fin=int(fin.timestamp()), station=station,
                          show=AVEC_EMISSION if avec_emission else "")


def lire_grille(session: requests.Session, cle: str, texte: str) -> list[dict]:
    """Envoie la requête et renvoie la liste des étapes de la grille."""
    r = session.post(RADIOFRANCE_API, params={"x-token": cle}, json={"query": texte}, timeout=DELAI)
    if r.status_code != 200:
        # Pas de r.url ni de r.request dans le message : ils contiennent la clé.
        raise ErreurRadioFrance(f"HTTP {r.status_code} : {r.text[:200]}")
    corps = r.json()
    erreurs = corps.get("errors") or []
    grille = (corps.get("data") or {}).get("grid")
    if grille is None:
        message = "; ".join(e.get("message", "") for e in erreurs) or "réponse sans grille"
        raise ErreurRadioFrance(message[:300])
    return grille


def _date(horodatage) -> datetime | None:
    return datetime.fromtimestamp(int(horodatage), PARIS) if horodatage else None


def collecter(config: Configuration, session: requests.Session, connexion, maintenant: datetime,
              cle: str | None = None) -> Rapport:
    rapport = Rapport()
    cle = cle or os.environ.get("RADIOFRANCE_API_KEY")
    stations = [c for c in config.chaines if c.plateforme == "radio"]
    if not stations:
        return rapport
    if not cle:
        rapport.interrompu = SANS_CLE
        return rapport
    maintenant = maintenant.astimezone(PARIS)
    fin_horizon = datetime.combine(maintenant.date() + timedelta(days=JOURS_AFFICHES), datetime.min.time(), PARIS)
    filtre = FiltrePolitique(config)
    couvertes: set[str] = set()
    avec_emission = True

    for chaine in stations:
        station = chaine.cle["station"]
        try:
            try:
                grille = lire_grille(session, cle, requete(station, maintenant, fin_horizon, avec_emission))
            except ErreurRadioFrance as e:
                if not avec_emission or "show" not in str(e):
                    raise
                avec_emission = False
                rapport.anomalies.append("Radio France : nom des émissions (« show ») refusé, titres seuls")
                grille = lire_grille(session, cle, requete(station, maintenant, fin_horizon, False))
        except (requests.RequestException, ValueError, ErreurRadioFrance) as e:
            # Une erreur réseau cite l'adresse, donc la clé : elle est masquée (base et journaux publics).
            rapport.anomalies.append(f"grille illisible : {chaine.nom} ({str(e).replace(cle, '***')})")
            continue
        rapport.stations_lues += 1
        couvertes.add(chaine.nom)
        for etape in grille:
            debut, fin = _date(etape.get("start")), _date(etape.get("end"))
            if debut is None or debut >= fin_horizon or (fin or debut) <= maintenant:
                continue
            if config.tv_heures_masquees and config.tv_heures_masquees[0] <= debut.hour < config.tv_heures_masquees[1]:
                rapport.masques += 1
                continue
            diffusion = etape.get("diffusion") or {}
            titre = (diffusion.get("title") or etape.get("title") or "").strip()
            emission = ((diffusion.get("show") or {}).get("title") or "").strip()
            if not (titre or emission):
                continue
            rapport.programmes += 1
            # Le nom de l'émission sert la liste blanche (« Questions politiques ») ; le titre
            # de la diffusion nomme souvent l'invité (« Gabriel Attal, invité de 8h20 »).
            if emission and titre and emission.casefold() not in titre.casefold():
                titre_complet, titre_filtre, description = f"{emission} — {titre}", emission, titre
            else:
                titre_complet = titre_filtre = titre or emission
                description = ""
            description = f"{description}\n{diffusion.get('standFirst') or ''}"
            decision = filtre.decider(chaine, titre_filtre, description)
            if decision is None:
                continue
            # Direct de la station d'abord, puis la page de la diffusion (réécoute).
            liens = list(chaine.direct)
            if diffusion.get("url") and diffusion["url"] not in liens:
                liens.append(diffusion["url"])
            rapport.retenues.append({
                "id": f"radio:{station}:{debut:%Y%m%d%H%M}",
                "titre": titre_complet,
                "debut": debut.isoformat(timespec="seconds"),
                "fin": fin.isoformat(timespec="seconds") if fin else None,
                "plateforme": "radio",
                "chaine": chaine.nom,
                "categorie": decision.categorie,
                "invites": decision.invites,
                "lien": liens,
                "statut": statut(debut, fin, maintenant),
                "filtre": decision.filtre,
                "motif": decision.motif,
            })

    if not couvertes:
        rapport.interrompu = "API Radio France inaccessible : " + "; ".join(rapport.anomalies)
        rapport.anomalies = []
    a_ecrire = [{k: v for k, v in e.items() if k != "motif"} for e in rapport.retenues]
    rapport.annulees = db.enregistrer_collecte(connexion, a_ecrire, "radio", couvertes, maintenant)
    return rapport
