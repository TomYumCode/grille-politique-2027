"""Collecteur Twitch : chaînes en direct maintenant et plannings publiés.

Appels par collecte : 1 jeton d'application, 1 appel « users » et 1 appel
« streams » par lot de 100 chaînes, puis 1 appel « schedule » par chaîne.
Beaucoup de streamers ne remplissent pas leur planning : l'état « en direct »
vérifié à chaque collecte rattrape les directs non annoncés.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import requests

from grille import db
from grille.acces import TWITCH_API, TWITCH_TOKEN
from grille.config import Chaine, Configuration
from grille.filtre import FiltrePolitique
from grille.tv import JOURS_AFFICHES, PARIS

DELAI = 30


@dataclass
class Rapport:
    chaines_lues: int = 0
    en_direct: int = 0
    creneaux: int = 0
    retenues: list[dict] = field(default_factory=list)
    annulees: int = 0
    directs_finis: int = 0
    anomalies: list[str] = field(default_factory=list)
    a_confirmer: dict[str, bool] = field(default_factory=dict)
    interrompu: str = ""
    douteux: int = 0


def _date(valeur: str | None) -> datetime | None:
    return datetime.fromisoformat(valeur.replace("Z", "+00:00")).astimezone(PARIS) if valeur else None


def _par_lots(liste: list, taille: int = 100):
    for i in range(0, len(liste), taille):
        yield liste[i:i + taille]


def collecter(config: Configuration, session: requests.Session, connexion, maintenant: datetime,
              client_id: str | None = None, secret: str | None = None) -> Rapport:
    rapport = Rapport()
    client_id = client_id or os.environ.get("TWITCH_CLIENT_ID")
    secret = secret or os.environ.get("TWITCH_CLIENT_SECRET")
    if not (client_id and secret):
        rapport.interrompu = "secrets TWITCH_CLIENT_ID et TWITCH_CLIENT_SECRET absents"
        return rapport
    maintenant = maintenant.astimezone(PARIS)
    fin_horizon = datetime.combine(maintenant.date() + timedelta(days=JOURS_AFFICHES), datetime.min.time(), PARIS)
    chaines = {c.cle["login"]: c for c in config.chaines if c.plateforme == "twitch"}
    filtre = FiltrePolitique(config)
    couvertes: set[str] = set()

    try:
        r = session.post(
            TWITCH_TOKEN,
            data={"client_id": client_id, "client_secret": secret, "grant_type": "client_credentials"},
            timeout=DELAI,
        )
        r.raise_for_status()
        en_tetes = {"Authorization": f"Bearer {r.json()['access_token']}", "Client-Id": client_id}

        def appeler(ressource: str, params) -> requests.Response:
            return session.get(f"{TWITCH_API}/{ressource}", params=params, headers=en_tetes, timeout=DELAI)

        # Logins → identifiants numériques (le planning les exige).
        identifiants: dict[str, str] = {}
        for lot in _par_lots(list(chaines)):
            r = appeler("users", [("login", login) for login in lot])
            r.raise_for_status()
            utilisateurs = r.json().get("data") or []
            identifiants.update({u["login"].lower(): u["id"] for u in utilisateurs})
            db.noter_logos(connexion, {chaines[u["login"].lower()].nom: u.get("profile_image_url", "")
                                       for u in utilisateurs if u["login"].lower() in chaines}, maintenant)
        for login, c in chaines.items():
            if login not in identifiants:
                rapport.anomalies.append(f"chaîne Twitch introuvable : {c.nom} ({c.adresse})")
            if c.a_confirmer:
                rapport.a_confirmer[c.nom] = login in identifiants

        # Qui est en direct maintenant ?
        for lot in _par_lots(list(identifiants.values())):
            r = appeler("streams", [("user_id", i) for i in lot] + [("first", "100")])
            r.raise_for_status()
            for flux in r.json().get("data") or []:
                rapport.en_direct += 1
                c = chaines.get(flux["user_login"].lower())
                if c:
                    _retenir(rapport, filtre, c, f"twitch:direct:{flux['id']}", flux.get("title", ""),
                             flux.get("game_name", ""), _date(flux["started_at"]), None, "en direct")

        # Plannings publiés.
        for login, identifiant in identifiants.items():
            c = chaines[login]
            try:
                r = appeler("schedule", {"broadcaster_id": identifiant, "first": "25"})
            except requests.RequestException as e:
                rapport.anomalies.append(f"planning Twitch illisible : {c.nom} ({e})")
                continue
            if r.status_code == 404:  # aucun planning publié
                rapport.chaines_lues += 1
                couvertes.add(c.nom)
                continue
            if r.status_code != 200:
                rapport.anomalies.append(f"planning Twitch illisible : {c.nom} (HTTP {r.status_code})")
                continue
            rapport.chaines_lues += 1
            couvertes.add(c.nom)
            for creneau in (r.json().get("data") or {}).get("segments") or []:
                debut, fin = _date(creneau["start_time"]), _date(creneau.get("end_time"))
                if creneau.get("canceled_until") or debut >= fin_horizon or (fin or debut) <= maintenant:
                    continue
                rapport.creneaux += 1
                categorie = (creneau.get("category") or {}).get("name", "")
                _retenir(rapport, filtre, c, f"twitch:{creneau['id']}:{debut:%Y%m%d%H%M}",
                         creneau.get("title", ""), categorie, debut, fin, "annoncé")
    except requests.RequestException as e:
        rapport.interrompu = f"API Twitch inaccessible ({e})"

    rapport.douteux = db.noter_douteux(connexion, filtre.douteux, maintenant)
    a_ecrire = [{k: v for k, v in e.items() if k != "motif"} for e in rapport.retenues]
    couvertes = set() if rapport.interrompu else couvertes
    rapport.annulees = db.enregistrer_collecte(connexion, a_ecrire, "twitch", couvertes, maintenant)
    ids_en_direct = {e["id"] for e in rapport.retenues if e["statut"] == "en direct"}
    rapport.directs_finis = db.terminer_directs(connexion, "twitch", ids_en_direct, couvertes, maintenant)
    return rapport


def _retenir(rapport: Rapport, filtre: FiltrePolitique, chaine: Chaine, id_: str, titre: str, categorie_jeu: str,
             debut: datetime, fin: datetime | None, etat: str) -> None:
    decision = filtre.decider(chaine, titre, categorie_jeu)
    if decision is None:
        filtre.noter_douteux(id_, "twitch", chaine, titre, categorie_jeu, debut)
        return
    rapport.retenues.append({
        "id": id_,
        "titre": titre,
        "debut": debut.isoformat(timespec="seconds"),
        "fin": fin.isoformat(timespec="seconds") if fin else None,
        "plateforme": "twitch",
        "chaine": chaine.nom,
        "categorie": decision.categorie,
        "invites": decision.invites,
        "lien": [chaine.adresse],
        "statut": etat,
        "filtre": decision.filtre,
        "motif": decision.motif,
    })
