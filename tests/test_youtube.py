"""Collecteur YouTube, à partir de réponses enregistrées de l'API."""

import shutil
from datetime import datetime
from pathlib import Path

import pytest

from grille import config, db, youtube
from grille.acces import YOUTUBE_API
from grille.tv import PARIS
from tests.session_factice import Reponse, Session, charger

MAINTENANT = datetime(2027, 3, 27, 10, 0, tzinfo=PARIS)  # veille du passage à l'heure d'été
API = charger("youtube_api.json")
CHAINES = """\
chaines:
- {plateforme: youtube, nom: "Hugo au Perchoir", adresse: "https://www.youtube.com/@HugoauPerchoir", categorie: "Interviews politiques (rediffusions)"}
- {plateforme: youtube, nom: "Clément Viktorovitch", adresse: "https://www.youtube.com/@Clemovitch", categorie: "Décryptage"}
- {plateforme: youtube, nom: "La France insoumise", adresse: "https://www.youtube.com/channel/UCKHKSD-yanY2ZwwU_4Tgf0w", categorie: "Parti"}
- {plateforme: youtube, nom: "Brut", adresse: "https://www.youtube.com/c/brutofficiel", categorie: "Média jeune", a_confirmer: true}
"""


@pytest.fixture
def conf(tmp_path):
    (tmp_path / "chaines.yaml").write_text(CHAINES, encoding="utf-8")
    shutil.copy(Path(config.DOSSIER_CONFIG) / "politique.yaml", tmp_path / "politique.yaml")
    return config.charger(tmp_path)


@pytest.fixture
def connexion(tmp_path):
    c = db.ouvrir(tmp_path / "grille.sqlite")
    yield c
    c.close()


def routeur(methode, url, params):
    ressource = url.removeprefix(YOUTUBE_API + "/")
    if ressource == "channels":
        if "forHandle" in params:
            return Reponse(corps=API[f"channels_forHandle_{params['forHandle']}"])
        # Recherche par identifiants : toutes les chaînes connues des réponses enregistrées.
        connues = [it for cle, rep in API.items() if cle.startswith("channels_") for it in rep.get("items", [])]
        demandes = params["id"].split(",")
        return Reponse(corps={**API["channels_id"], "items": [it for it in connues if it["id"] in demandes]})
    if ressource == "playlistItems":
        return Reponse(corps=API[f"playlistItems_{params['playlistId']}"])
    if ressource == "videos":
        demandes = params["id"].split(",")
        return Reponse(corps={**API["videos"], "items": [v for v in API["videos"]["items"] if v["id"] in demandes]})
    raise AssertionError(url)


def test_direct_programme_a_la_bonne_heure_de_paris(conf, connexion):
    rapport = youtube.collecter(conf, Session(routeur), connexion, MAINTENANT, cle_api="cle")
    assert not rapport.interrompu
    retenues = {e["id"]: e for e in rapport.retenues}
    assert set(retenues) == {"youtube:direct_perchoir", "youtube:annonce_heure_ete", "youtube:meeting_termine"}

    # Programmé à 18:00 UTC le 28 mars 2027, jour du passage à l'heure d'été : 20:00 à Paris.
    annonce = retenues["youtube:annonce_heure_ete"]
    assert annonce["debut"] == "2027-03-28T20:00:00+02:00"
    assert (annonce["statut"], annonce["filtre"]) == ("annoncé", "mots-clés")
    assert annonce["invites"] == ["Raphaël Glucksmann"]
    assert annonce["lien"] == ["https://www.youtube.com/watch?v=annonce_heure_ete"]

    direct = retenues["youtube:direct_perchoir"]
    assert (direct["statut"], direct["filtre"], direct["debut"]) == ("en direct", "liste blanche", "2027-03-27T09:30:00+01:00")
    assert retenues["youtube:meeting_termine"]["statut"] == "terminé"

    # En base, avec la même heure de Paris.
    debut = connexion.execute("SELECT debut FROM emissions WHERE id = 'youtube:annonce_heure_ete'").fetchone()[0]
    assert debut == "2027-03-28T20:00:00+02:00"


def test_chaine_c_introuvable_signalee(conf, connexion):
    rapport = youtube.collecter(conf, Session(routeur), connexion, MAINTENANT, cle_api="cle")
    assert rapport.a_confirmer == {"Brut": False}
    assert any("Brut" in a and "@pseudo" in a for a in rapport.anomalies)
    assert rapport.chaines_lues == 3


def test_quota_economise(conf, connexion):
    session = Session(routeur)
    rapport = youtube.collecter(conf, session, connexion, MAINTENANT, cle_api="cle")
    # 1 lot d'identifiants UC + 3 pseudos (dont Brut) + 3 playlists + 1 lot de vidéos
    assert rapport.unites == 8
    # Seconde collecte : chaînes déjà résolues, mais Brut (introuvable) est retenté.
    session2 = Session(routeur)
    rapport2 = youtube.collecter(conf, session2, connexion, MAINTENANT, cle_api="cle")
    assert rapport2.unites == 5
    assert all("search" not in url for _, url, _ in session.appels + session2.appels)


def test_direct_sorti_de_la_playlist_reste_suivi(conf, connexion):
    youtube.collecter(conf, Session(routeur), connexion, MAINTENANT, cle_api="cle")

    def sans_annonce(methode, url, params):
        if url.endswith("/playlistItems") and params["playlistId"] == "UUclemovitch00000000000":
            return Reponse(corps={"items": [{"contentDetails": {"videoId": "annonce_non_politique"}}]})
        return routeur(methode, url, params)

    session = Session(sans_annonce)
    youtube.collecter(conf, session, connexion, MAINTENANT, cle_api="cle")
    ids_demandes = [p["id"] for _, url, p in session.appels if url.endswith("/videos")][0]
    assert "annonce_heure_ete" in ids_demandes
    statut = connexion.execute("SELECT statut FROM emissions WHERE id = 'youtube:annonce_heure_ete'").fetchone()[0]
    assert statut == "annoncé"


def test_quota_epuise_n_annule_rien(conf, connexion):
    youtube.collecter(conf, Session(routeur), connexion, MAINTENANT, cle_api="cle")

    def quota(methode, url, params):
        if url.endswith("/videos"):
            return Reponse(403, {"error": {"errors": [{"reason": "quotaExceeded"}]}})
        return routeur(methode, url, params)

    rapport = youtube.collecter(conf, Session(quota), connexion, MAINTENANT, cle_api="cle")
    assert "quota" in rapport.interrompu
    statut = connexion.execute("SELECT statut FROM emissions WHERE id = 'youtube:annonce_heure_ete'").fetchone()[0]
    assert statut == "annoncé"


def test_sans_cle(conf, connexion, monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    assert "YOUTUBE_API_KEY" in youtube.collecter(conf, Session(routeur), connexion, MAINTENANT).interrompu


def test_logos_memorises(conf, connexion):
    youtube.collecter(conf, Session(routeur), connexion, MAINTENANT, cle_api="cle")
    logos = db.logos(connexion)
    assert logos["Hugo au Perchoir"] == "https://yt3.ggpht.com/perchoir=s88-c-k-c0x00ffffff-no-rj"
    assert set(logos) == {"Hugo au Perchoir", "Clément Viktorovitch", "La France insoumise"}


def test_logo_rattrape_pour_les_chaines_deja_connues(conf, connexion):
    youtube.collecter(conf, Session(routeur), connexion, MAINTENANT, cle_api="cle")
    connexion.execute("DELETE FROM logos")  # base d'avant les logos
    session = Session(routeur)
    youtube.collecter(conf, session, connexion, MAINTENANT, cle_api="cle")
    appels_logos = [p for _, url, p in session.appels if url.endswith("/channels") and p.get("part") == "snippet"]
    assert len(appels_logos) == 1  # un seul appel pour toutes les chaînes
    assert "Hugo au Perchoir" in db.logos(connexion)


def test_texte_de_presentation_de_la_chaine_ignore():
    """Tocsin met dans chaque description « La présidentielle arrive à grands pas… » :
    ce texte commun ne doit pas faire classer chaque matinale dans la présidentielle."""
    pub = ("🔔🔔 TOCSIN EN PREMIÈRE LIGNE CONTRE LA CENSURE 🔔🔔\n"
           "La présidentielle arrive à grands pas, et la censure avec elle !\n"
           "Soutenez-nous, faites un don à Tocsin : https://tocsin-media.fr/nous")
    videos = [
        {"id": "a", "snippet": {"channelId": "UCtocsin", "description": pub + "\nAu sommaire : la BCE et la dette"}},
        {"id": "b", "snippet": {"channelId": "UCtocsin", "description": pub + "\nAu sommaire : Mai 68 et les lycéens"}},
        # Une autre chaîne qui cite la présidentielle une seule fois garde sa description.
        {"id": "c", "snippet": {"channelId": "UCautre", "description": "Débat : la présidentielle vue des régions"}},
    ]
    youtube.sans_presentation(videos)
    assert videos[0]["snippet"]["description"] == "Au sommaire : la BCE et la dette"
    assert videos[1]["snippet"]["description"].endswith("Mai 68 et les lycéens")
    assert videos[2]["snippet"]["description"] == "Débat : la présidentielle vue des régions"


def test_video_ecartee_a_la_relecture_sort_de_la_grille(tmp_path):
    connexion = db.ouvrir(tmp_path / "g.sqlite")
    debut = datetime(2026, 10, 14, 7, 34, tzinfo=PARIS)
    db.enregistrer_collecte(connexion, [{
        "id": "youtube:tocsin1", "titre": "La Matinale du 14/10", "debut": debut.isoformat(), "fin": None,
        "plateforme": "youtube", "chaine": "Tocsin", "categorie": "analyse", "invites": [], "lien": [],
        "statut": "en direct", "filtre": "mots-clés"}], "youtube", set(), debut)
    assert db.annuler(connexion, ["youtube:tocsin1", "youtube:inconnue"], debut) == 1
    assert db.lister(connexion, debut.replace(hour=0), debut.replace(hour=23)) == []
    connexion.close()
