"""Collecteur YouTube : directs programmés, en cours et du jour des chaînes suivies.

Coût en quota, par collecte (limite par défaut : 10 000 unités par jour) :
- 1 unité par chaîne : playlistItems.list sur la playlist des vidéos mises en ligne ;
- 1 unité par lot de 50 vidéos : videos.list (titre, état du direct, heures) ;
- une seule fois par chaîne : channels.list pour trouver cette playlist (mémorisé en base).
search.list (100 unités) n'est jamais utilisé.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import requests

from grille import db
from grille.acces import YOUTUBE_API
from grille.config import Chaine, Configuration
from grille.filtre import FiltrePolitique
from grille.tv import JOURS_AFFICHES, PARIS, statut

DELAI = 30
VIDEOS_PAR_CHAINE = 15  # vidéos récentes examinées par chaîne
# Un direct annoncé dont l'heure est passée depuis plus longtemps a été abandonné sans être supprimé.
RETARD_MAXIMAL = timedelta(hours=6)


class QuotaEpuise(Exception):
    pass


@dataclass
class Rapport:
    chaines_lues: int = 0
    videos_examinees: int = 0
    retenues: list[dict] = field(default_factory=list)
    annulees: int = 0
    anomalies: list[str] = field(default_factory=list)
    a_confirmer: dict[str, bool] = field(default_factory=dict)  # nom → chaîne trouvée ?
    unites: int = 0  # quota consommé
    interrompu: str = ""
    douteux: int = 0  # nouveaux cas douteux


class ClientYouTube:
    def __init__(self, session: requests.Session, cle_api: str):
        self.session = session
        self.cle_api = cle_api
        self.unites = 0

    def appeler(self, ressource: str, **params) -> dict:
        self.unites += 1
        r = self.session.get(f"{YOUTUBE_API}/{ressource}", params={**params, "key": self.cle_api}, timeout=DELAI)
        if r.status_code == 403 and "quotaExceeded" in r.text:
            raise QuotaEpuise("quota YouTube du jour épuisé, reprise après minuit (heure du Pacifique)")
        if r.status_code == 404:
            return {"items": []}
        r.raise_for_status()
        return r.json()


def _resoudre(client: ClientYouTube, chaines: list[Chaine], connexion, rapport: Rapport) -> dict[str, tuple[str, str]]:
    """Adresse → (identifiant UC…, playlist UU…), en ne payant que pour les chaînes jamais vues."""
    connues = {a: (i, p) for a, i, p in connexion.execute("SELECT adresse, identifiant, playlist FROM chaines_resolues")}
    maintenant = datetime.now(PARIS).isoformat(timespec="seconds")

    logos_connus = db.logos(connexion, avec_vides=True)
    nouveaux_logos: dict[str, str] = {}

    def memoriser(chaine: Chaine, item: dict) -> None:
        resolution = (item["id"], item["contentDetails"]["relatedPlaylists"]["uploads"])
        connues[chaine.adresse] = resolution
        connexion.execute(
            "INSERT OR REPLACE INTO chaines_resolues VALUES (?, ?, ?, ?)", (chaine.adresse, *resolution, maintenant)
        )
        nouveaux_logos[chaine.nom] = _logo(item)

    a_resoudre = [c for c in chaines if c.adresse not in connues]
    # Identifiants UC… déjà connus : un seul appel pour 50 chaînes.
    par_id = [c for c in a_resoudre if "channel_id" in c.cle]
    for i in range(0, len(par_id), 50):
        lot = par_id[i:i + 50]
        items = client.appeler("channels", part="snippet,contentDetails", id=",".join(c.cle["channel_id"] for c in lot))
        trouves = {it["id"]: it for it in items.get("items") or []}
        for c in lot:
            if c.cle["channel_id"] in trouves:
                memoriser(c, trouves[c.cle["channel_id"]])
    # Pseudos @…, anciens noms d'utilisateur /user/…, adresses personnalisées /c/… :
    # l'API n'a pas de recherche par /c/…, on essaie comme pseudo (c'est souvent le même).
    for c in a_resoudre:
        if c.adresse in connues or "channel_id" in c.cle:
            continue
        if "user" in c.cle:
            items = client.appeler("channels", part="snippet,contentDetails", forUsername=c.cle["user"])
        else:
            items = client.appeler("channels", part="snippet,contentDetails",
                                   forHandle=c.cle.get("handle") or c.cle["custom"])
        if items.get("items"):
            memoriser(c, items["items"][0])
    # Chaînes résolues avant l'arrivée des logos : un appel pour 50 chaînes, une seule fois.
    sans_logo = [c for c in chaines if c.adresse in connues and c.nom not in logos_connus and c.nom not in nouveaux_logos]
    for i in range(0, len(sans_logo), 50):
        lot = sans_logo[i:i + 50]
        items = client.appeler("channels", part="snippet", id=",".join(connues[c.adresse][0] for c in lot))
        par_id = {it["id"]: it for it in items.get("items") or []}
        for c in lot:
            if connues[c.adresse][0] in par_id:
                nouveaux_logos[c.nom] = _logo(par_id[connues[c.adresse][0]])
    db.noter_logos(connexion, nouveaux_logos, datetime.now(PARIS))
    connexion.commit()

    for c in chaines:
        if c.adresse not in connues:
            conseil = " : remplacer par l'adresse en @pseudo de la chaîne" if "custom" in c.cle else ""
            rapport.anomalies.append(f"chaîne YouTube introuvable : {c.nom} ({c.adresse}){conseil}")
        if c.a_confirmer:
            rapport.a_confirmer[c.nom] = c.adresse in connues
    return connues


def _logo(item: dict) -> str:
    """Plus petite vignette de la chaîne (88 px), suffisante pour un logo."""
    vignettes = (item.get("snippet") or {}).get("thumbnails") or {}
    for taille in ("default", "medium", "high"):
        if vignettes.get(taille, {}).get("url"):
            return vignettes[taille]["url"]
    return ""


def _date(valeur: str | None) -> datetime | None:
    return datetime.fromisoformat(valeur.replace("Z", "+00:00")).astimezone(PARIS) if valeur else None


def _en_cours_en_base(connexion) -> list[str]:
    return [
        i.removeprefix("youtube:")
        for (i,) in connexion.execute(
            "SELECT id FROM emissions WHERE plateforme = 'youtube' AND statut IN ('annoncé', 'en direct')"
        )
    ]


def collecter(config: Configuration, session: requests.Session, connexion, maintenant: datetime,
              cle_api: str | None = None) -> Rapport:
    rapport = Rapport()
    cle_api = cle_api or os.environ.get("YOUTUBE_API_KEY")
    if not cle_api:
        rapport.interrompu = "secret YOUTUBE_API_KEY absent"
        return rapport
    maintenant = maintenant.astimezone(PARIS)
    debut_du_jour = datetime.combine(maintenant.date(), datetime.min.time(), PARIS)
    fin_horizon = debut_du_jour + timedelta(days=JOURS_AFFICHES)
    chaines = [c for c in config.chaines if c.plateforme == "youtube"]
    client = ClientYouTube(session, cle_api)
    filtre = FiltrePolitique(config)
    couvertes: set[str] = set()

    try:
        resolues = _resoudre(client, chaines, connexion, rapport)
        chaine_de_la_video: dict[str, Chaine] = {}
        for c in chaines:
            if c.adresse not in resolues:
                continue
            try:
                items = client.appeler(
                    "playlistItems", part="contentDetails", playlistId=resolues[c.adresse][1],
                    maxResults=VIDEOS_PAR_CHAINE,
                )
            except requests.RequestException as e:
                rapport.anomalies.append(f"chaîne YouTube illisible : {c.nom} ({e})")
                continue
            rapport.chaines_lues += 1
            couvertes.add(c.nom)
            for it in items.get("items") or []:
                chaine_de_la_video[it["contentDetails"]["videoId"]] = c
        # On relit aussi les directs déjà en base : ils ont pu sortir des 15 dernières vidéos.
        ids_en_cours = _en_cours_en_base(connexion)
        identifiants = list(dict.fromkeys(list(chaine_de_la_video) + ids_en_cours))
        par_canal = {resolues[c.adresse][0]: c for c in chaines if c.adresse in resolues}
        for i in range(0, len(identifiants), 50):
            lot = identifiants[i:i + 50]
            reponse = client.appeler("videos", part="snippet,liveStreamingDetails", id=",".join(lot), maxResults=50)
            for video in reponse.get("items") or []:
                rapport.videos_examinees += 1
                chaine = chaine_de_la_video.get(video["id"]) or par_canal.get(video["snippet"]["channelId"])
                if chaine is None:
                    continue
                emission = _emission(video, chaine, filtre, maintenant, debut_du_jour, fin_horizon)
                if emission:
                    rapport.retenues.append(emission)
    except QuotaEpuise as e:
        rapport.interrompu = str(e)
    except requests.RequestException as e:
        rapport.interrompu = f"API YouTube inaccessible ({e})"

    rapport.unites = client.unites
    rapport.douteux = db.noter_douteux(connexion, filtre.douteux, maintenant)
    a_ecrire = [{k: v for k, v in e.items() if k != "motif"} for e in rapport.retenues]
    # Collecte interrompue : on écrit ce qu'on a, mais on n'annule rien.
    rapport.annulees = db.enregistrer_collecte(
        connexion, a_ecrire, "youtube", set() if rapport.interrompu else couvertes, maintenant
    )
    return rapport


def _emission(video: dict, chaine: Chaine, filtre: FiltrePolitique, maintenant: datetime,
              debut_du_jour: datetime, fin_horizon: datetime) -> dict | None:
    details = video.get("liveStreamingDetails")
    etat = video["snippet"].get("liveBroadcastContent")
    if not details:
        return None  # vidéo ordinaire, ni direct ni première
    prevu, reel_debut, reel_fin = (_date(details.get(k)) for k in
                                   ("scheduledStartTime", "actualStartTime", "actualEndTime"))
    debut = reel_debut or prevu
    if debut is None or debut >= fin_horizon:
        return None
    if etat == "upcoming" and debut < maintenant - RETARD_MAXIMAL:
        return None  # annonce abandonnée
    if etat not in ("upcoming", "live") and (reel_fin is None or reel_fin < debut_du_jour):
        return None  # direct terminé avant aujourd'hui
    fin = reel_fin or _date(details.get("scheduledEndTime"))
    titre = video["snippet"].get("title", "")
    decision = filtre.decider(chaine, titre, video["snippet"].get("description", ""))
    if decision is None:
        filtre.noter_douteux(f"youtube:{video['id']}", "youtube", chaine, titre,
                             video["snippet"].get("description", ""), debut)
        return None
    if etat == "live":
        etat_emission = "en direct"
    elif etat == "upcoming":
        etat_emission = "annoncé"
    else:
        etat_emission = statut(debut, fin, maintenant)
    return {
        "id": f"youtube:{video['id']}",
        "titre": titre,
        "debut": debut.isoformat(timespec="seconds"),
        "fin": fin.isoformat(timespec="seconds") if fin else None,
        "plateforme": "youtube",
        "chaine": chaine.nom,
        "categorie": decision.categorie,
        "invites": decision.invites,
        "cites": decision.cites,
        "resume": video["snippet"].get("description", ""),
        "lien": [f"https://www.youtube.com/watch?v={video['id']}"],
        "statut": etat_emission,
        "filtre": decision.filtre,
        "motif": decision.motif,
    }
