"""Vérification des accès aux sources : clés présentes, réponses des API.

Points d'accès confirmés le 8 octobre 2026 (voir docs/VERIFICATIONS.md).
Chaque vérification renvoie un Resultat et n'interrompt jamais les autres.
"""

from __future__ import annotations

import os
import zlib
from dataclasses import dataclass

import requests

from grille.config import Configuration

YOUTUBE_API = "https://youtube.googleapis.com/youtube/v3"
YOUTUBE_QUOTA_JOUR = 10_000
TWITCH_TOKEN = "https://id.twitch.tv/oauth2/token"
TWITCH_API = "https://api.twitch.tv/helix"
XMLTV_TNT = "https://xmltvfr.fr/xmltv/xmltv_tnt.xml.gz"
RADIOFRANCE_API = "https://openapi.radiofrance.fr/v1/graphql"
FRANCETVPRO = "https://www.francetvpro.fr/contenu-de-presse"

DELAI = 20  # secondes


@dataclass
class Resultat:
    source: str
    etat: str  # "ok", "non configuré" ou "erreur"
    detail: str


def _erreur_http(reponse: requests.Response) -> str:
    return f"HTTP {reponse.status_code} : {reponse.text[:300]}"


def estimer_quota_youtube(nb_chaines: int, collectes_par_jour: int = 24) -> int:
    """Unités par jour : 1 playlistItems.list par chaîne, plus 1 videos.list par lot de 50 vidéos.

    Le collecteur examine les 15 dernières vidéos de chaque chaîne. channels.list
    ne sert qu'une fois par chaîne (résultat mémorisé en base) ; search.list
    (100 unités) n'est jamais utilisé.
    """
    lots_de_videos = -(-nb_chaines * 15 // 50)
    return (nb_chaines + lots_de_videos) * collectes_par_jour


def verifier_youtube(config: Configuration, session: requests.Session) -> Resultat:
    cle_api = os.environ.get("YOUTUBE_API_KEY")
    if not cle_api:
        return Resultat("YouTube", "non configuré", "secret YOUTUBE_API_KEY absent")
    chaine = next((c for c in config.chaines if c.plateforme == "youtube" and "handle" in c.cle), None)
    if chaine is None:
        return Resultat("YouTube", "erreur", "aucune chaîne YouTube avec @pseudo dans chaines.yaml")
    try:
        r = session.get(
            f"{YOUTUBE_API}/channels",
            params={"part": "contentDetails", "forHandle": chaine.cle["handle"], "key": cle_api},
            timeout=DELAI,
        )
    except requests.RequestException as e:
        return Resultat("YouTube", "erreur", f"réseau : {e}")
    if r.status_code != 200:
        return Resultat("YouTube", "erreur", _erreur_http(r))
    items = r.json().get("items") or []
    if not items:
        return Resultat("YouTube", "erreur", f"clé acceptée, mais chaîne @{chaine.cle['handle']} introuvable")
    playlist = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    nb = sum(1 for c in config.chaines if c.plateforme == "youtube")
    besoin = estimer_quota_youtube(nb)
    return Resultat(
        "YouTube",
        "ok",
        f"@{chaine.cle['handle']} → playlist {playlist} ; quota estimé {besoin} unités/jour "
        f"pour {nb} chaînes (limite par défaut {YOUTUBE_QUOTA_JOUR})",
    )


def verifier_twitch(config: Configuration, session: requests.Session) -> Resultat:
    client_id = os.environ.get("TWITCH_CLIENT_ID")
    secret = os.environ.get("TWITCH_CLIENT_SECRET")
    if not (client_id and secret):
        return Resultat("Twitch", "non configuré", "secrets TWITCH_CLIENT_ID et TWITCH_CLIENT_SECRET absents")
    try:
        r = session.post(
            TWITCH_TOKEN,
            data={"client_id": client_id, "client_secret": secret, "grant_type": "client_credentials"},
            timeout=DELAI,
        )
        if r.status_code != 200:
            return Resultat("Twitch", "erreur", "jeton refusé, " + _erreur_http(r))
        jeton = r.json()["access_token"]
        logins = [c.cle["login"] for c in config.chaines if c.plateforme == "twitch"][:100]
        r = session.get(
            f"{TWITCH_API}/users",
            params=[("login", login) for login in logins],
            headers={"Authorization": f"Bearer {jeton}", "Client-Id": client_id},
            timeout=DELAI,
        )
    except requests.RequestException as e:
        return Resultat("Twitch", "erreur", f"réseau : {e}")
    if r.status_code != 200:
        return Resultat("Twitch", "erreur", _erreur_http(r))
    trouves = {u["login"].lower() for u in r.json().get("data") or []}
    absents = sorted(set(logins) - trouves)
    detail = f"jeton d'application obtenu ; {len(trouves)}/{len(logins)} comptes trouvés"
    if absents:
        detail += " ; introuvables : " + ", ".join(absents)
    return Resultat("Twitch", "ok", detail)


def verifier_radiofrance(config: Configuration, session: requests.Session) -> Resultat:
    stations = [c.cle["station"] for c in config.chaines if c.plateforme == "radio"]
    if not stations:
        return Resultat("Radio France", "non configuré", "aucune station radio dans chaines.yaml")
    cle = os.environ.get("RADIOFRANCE_API_KEY")
    if not cle:
        return Resultat("Radio France", "non configuré", "secret RADIOFRANCE_API_KEY absent")
    try:
        # La clé passe dans l'adresse : elle est masquée dans tout message affiché.
        r = session.post(RADIOFRANCE_API, params={"x-token": cle}, json={"query": "{ brands { id title } }"},
                         timeout=DELAI)
    except requests.RequestException as e:
        return Resultat("Radio France", "erreur", f"réseau : {str(e).replace(cle, '***')}")
    if r.status_code != 200:
        return Resultat("Radio France", "erreur", _erreur_http(r).replace(cle, "***"))
    marques = {b.get("id") for b in (r.json().get("data") or {}).get("brands") or []}
    if not marques:
        return Resultat("Radio France", "erreur", "clé acceptée, mais liste des stations vide")
    absentes = sorted(set(stations) - marques)
    detail = f"clé acceptée ; {len(stations) - len(absentes)}/{len(stations)} stations reconnues"
    if absentes:
        return Resultat("Radio France", "erreur", detail + " ; inconnues : " + ", ".join(absentes)
                        + " (codes possibles : " + ", ".join(sorted(m for m in marques if m)) + ")")
    return Resultat("Radio France", "ok", detail)


def verifier_xmltv(session: requests.Session) -> Resultat:
    try:
        with session.get(XMLTV_TNT, stream=True, timeout=DELAI) as r:
            if r.status_code != 200:
                return Resultat("Télévision (XMLTV)", "erreur", _erreur_http(r))
            debut = r.raw.read(64 * 1024)
            maj = r.headers.get("Last-Modified", "date inconnue")
    except requests.RequestException as e:
        return Resultat("Télévision (XMLTV)", "erreur", f"réseau : {e}")
    try:
        texte = _decompresser_debut(debut)
    except (OSError, zlib.error):
        return Resultat("Télévision (XMLTV)", "erreur", "le fichier reçu n'est pas au format gzip")
    if b"<tv" not in texte:
        return Resultat("Télévision (XMLTV)", "erreur", "le fichier reçu ne ressemble pas à du XMLTV")
    return Resultat("Télévision (XMLTV)", "ok", f"{XMLTV_TNT} lisible (mis à jour : {maj})")


def _decompresser_debut(donnees: bytes) -> bytes:
    """Décompresse le début d'un fichier gzip tronqué."""
    if donnees[:2] != b"\x1f\x8b":
        raise OSError("pas de signature gzip")
    return zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(donnees)


def verifier_tout(config: Configuration, session: requests.Session | None = None) -> list[Resultat]:
    session = session or requests.Session()
    return [verifier_xmltv(session), verifier_radiofrance(config, session), verifier_youtube(config, session),
            verifier_twitch(config, session)]
