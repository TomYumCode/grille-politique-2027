"""Collecteur radio : grille des programmes de l'API ouverte de Radio France.

Requête GraphQL « grid » par station (France Inter, franceinfo, France Culture…) et par
jour : l'API refuse plus de 24 heures par requête. Chaque collecte lit aujourd'hui, demain
et un des jours suivants à tour de rôle (chaque jour relu au moins toutes les 6 heures) :
3 stations × 3 jours × 24 collectes = 216 requêtes par jour (limite : 1 000). Un jour dont
des créneaux sont encore vides coûte une requête de plus (la même journée, une semaine plus
tôt) : au plus 432 requêtes par jour. La clé passe dans l'adresse (`?x-token=…`) : ne
jamais afficher l'adresse complète, les journaux de GitHub sont publics.

Forme de la requête reprise d'une intégration publique (voir docs/VERIFICATIONS.md) ;
la documentation officielle n'était pas joignable pendant le développement. Le champ
`show` (nom de l'émission) n'y figurait pas : s'il est refusé, le collecteur refait
la requête sans lui et le signale.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import requests

from grille import db
from grille.acces import RADIOFRANCE_API
from grille.config import Configuration
from grille.filtre import FiltrePolitique
from grille.radios_privees import jours_a_lire
from grille.tv import JOURS_AFFICHES, PARIS, statut

DELAI = 30
# L'API répond « You can't retrieve more than 24hours » au-delà.
FENETRE_MAX = timedelta(hours=24) - timedelta(seconds=1)
RESTE_MIN = timedelta(minutes=1)  # la dernière seconde du jour ne vaut pas une requête

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
    douteux: int = 0


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


def fenetres(jour: date) -> list[tuple[datetime, datetime]]:
    """Créneaux de requête couvrant un jour de Paris (deux le jour du passage à l'heure d'hiver, qui dure 25 h).
    Calcul en heure universelle : entre deux heures de Paris, Python compte l'heure affichée, pas la durée."""
    debut = datetime.combine(jour, datetime.min.time(), PARIS).astimezone(timezone.utc)
    fin_du_jour = datetime.combine(jour + timedelta(days=1), datetime.min.time(), PARIS).astimezone(timezone.utc)
    resultat = []
    while fin_du_jour - debut >= RESTE_MIN:
        fin = min(debut + FENETRE_MAX, fin_du_jour)
        resultat.append((debut.astimezone(PARIS), fin.astimezone(PARIS)))
        debut = fin
    return resultat


def _date(horodatage) -> datetime | None:
    return datetime.fromtimestamp(int(horodatage), PARIS) if horodatage else None


def _vide(etape: dict) -> bool:
    """Créneau de diffusion pas encore relié à sa diffusion (l'API renvoie « diffusion: null »)."""
    return "diffusion" in etape and not etape["diffusion"]


def emissions_par_heure(etapes: list[dict]) -> dict[str, str]:
    """Nom de l'émission de chaque créneau, par heure de début à Paris (« 18:20 »)."""
    noms = {}
    for e in etapes:
        nom = (((e.get("diffusion") or {}).get("show") or {}).get("title") or "").strip()
        if nom and (debut := _date(e.get("start"))):
            noms[f"{debut:%H:%M}"] = nom
    return noms


def collecter(config: Configuration, session: requests.Session, connexion, maintenant: datetime,
              cle: str | None = None) -> Rapport:
    rapport = Rapport()
    cle = cle or os.environ.get("RADIOFRANCE_API_KEY")
    stations = [c for c in config.chaines if c.plateforme == "radio" and "station" in c.cle]
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
    jours = set(jours_a_lire(maintenant))

    def lire_jour(station: str, jour: date) -> list[dict]:
        nonlocal avec_emission
        resultat = []
        for debut_f, fin_f in fenetres(jour):
            try:
                etapes = lire_grille(session, cle, requete(station, debut_f, fin_f, avec_emission))
            except ErreurRadioFrance as e:
                if not avec_emission or "show" not in str(e):
                    raise
                avec_emission = False
                rapport.anomalies.append("Radio France : nom des émissions (« show ») refusé, titres seuls")
                etapes = lire_grille(session, cle, requete(station, debut_f, fin_f, False))
            # Une étape à cheval sur deux créneaux n'est gardée qu'une fois : celui où elle commence.
            resultat += [e for e in etapes if (d := _date(e.get("start"))) and debut_f <= d < fin_f]
        return resultat

    for chaine in stations:
        station = chaine.cle["station"]
        grille = []
        try:
            for jour in sorted(jours):
                etapes = lire_jour(station, jour)
                # Radio France ne relie la diffusion à son créneau qu'au dernier moment (parfois
                # pendant l'émission) : d'ici là, le créneau est vide. Il prend le nom de l'émission
                # diffusée à la même heure une semaine plus tôt (« Questions du soir : le débat »).
                if any(_vide(e) for e in etapes):
                    modele = emissions_par_heure(lire_jour(station, jour - timedelta(days=7)))
                    for e in etapes:
                        if _vide(e) and (nom := modele.get(f"{_date(e['start']):%H:%M}")):
                            e["emission_presumee"] = nom
                grille += etapes
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
            emission = ((diffusion.get("show") or {}).get("title") or etape.get("emission_presumee") or "").strip()
            if not (titre or emission):
                continue
            rapport.programmes += 1
            # Le nom de l'émission sert la liste blanche (« Questions politiques ») ; le titre
            # de la diffusion nomme souvent l'invité (« Gabriel Attal, invité de 8h20 »).
            if emission and titre and emission.casefold() not in titre.casefold():
                titre_complet, titre_filtre, sous_titre = f"{emission} — {titre}", emission, titre
            else:
                titre_complet = titre_filtre = titre or emission
                sous_titre = ""
            resume = diffusion.get("standFirst") or ""
            description = f"{sous_titre}\n{resume}"
            decision = filtre.decider(chaine, titre_filtre, resume, sous_titre=sous_titre)
            if decision is None:
                filtre.noter_douteux(f"radio:{station}:{debut:%Y%m%d%H%M}", "radio", chaine, titre_complet,
                                     description, debut)
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
                "cites": decision.cites,
                "resume": resume,
                "lien": liens,
                "statut": statut(debut, fin, maintenant),
                "filtre": decision.filtre,
                "motif": decision.motif,
            })

    rapport.douteux = db.noter_douteux(connexion, filtre.douteux, maintenant)
    if not couvertes:
        rapport.interrompu = "API Radio France inaccessible : " + "; ".join(rapport.anomalies)
        rapport.anomalies = []
    a_ecrire = [{k: v for k, v in e.items() if k != "motif"} for e in rapport.retenues]
    # Seuls les jours relus peuvent voir des émissions passer en « annulé ».
    rapport.annulees = db.enregistrer_collecte(connexion, a_ecrire, "radio", couvertes, maintenant, jours)
    return rapport
