"""Collecteur Twitch, à partir de réponses enregistrées de l'API Helix."""

import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from grille import config, db, twitch
from grille.acces import TWITCH_API, TWITCH_TOKEN
from grille.tv import PARIS
from tests.session_factice import Reponse, Session, charger

MAINTENANT = datetime(2027, 3, 27, 10, 0, tzinfo=PARIS)
API = charger("twitch_api.json")
CHAINES = """\
chaines:
- {plateforme: twitch, nom: "BackSeat (Jean Massiet)", adresse: "https://www.twitch.tv/jeanmassiet", categorie: "Décryptage"}
- {plateforme: twitch, nom: "Hugo au Perchoir", adresse: "https://www.twitch.tv/hugoauperchoir", categorie: "Interviews politiques"}
- {plateforme: twitch, nom: "Usul", adresse: "https://www.twitch.tv/usul2000", categorie: "Gauche", a_confirmer: true}
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


def routeur(directs="streams"):
    def repondre(methode, url, params):
        if url == TWITCH_TOKEN:
            return Reponse(corps=API["token"])
        ressource = url.removeprefix(TWITCH_API + "/")
        if ressource == "users":
            return Reponse(corps=API["users"])
        if ressource == "streams":
            return Reponse(corps=API[directs] if directs else {"data": [], "pagination": {}})
        if ressource == "schedule":
            cle = f"schedule_{params['broadcaster_id']}"
            return Reponse(corps=API[cle]) if cle in API else Reponse(404, {"error": "Not Found", "status": 404})
        raise AssertionError(url)
    return repondre


def _collecter(conf, connexion, session, maintenant=MAINTENANT):
    return twitch.collecter(conf, session, connexion, maintenant, client_id="id", secret="secret")


def test_planning_et_direct(conf, connexion):
    session = Session(routeur())
    rapport = _collecter(conf, connexion, session)
    assert not rapport.interrompu
    retenues = {e["id"]: e for e in rapport.retenues}
    assert set(retenues) == {"twitch:direct:4242", "twitch:seg-presidentielle:202703282000"}

    # 18:00 UTC le 28 mars 2027 (passage à l'heure d'été) : 20:00 à Paris.
    creneau = retenues["twitch:seg-presidentielle:202703282000"]
    assert (creneau["debut"], creneau["fin"]) == ("2027-03-28T20:00:00+02:00", "2027-03-28T22:00:00+02:00")
    assert (creneau["statut"], creneau["categorie"]) == ("annoncé", "débat")
    assert creneau["lien"] == ["https://www.twitch.tv/jeanmassiet"]

    direct = retenues["twitch:direct:4242"]
    assert (direct["statut"], direct["filtre"], direct["invites"]) == ("en direct", "liste blanche", ["Marine Tondelier"])
    assert direct["debut"] == "2027-03-27T09:45:00+01:00"

    assert rapport.a_confirmer == {"Usul": False}
    assert rapport.chaines_lues == 2  # Hugo au Perchoir n'a pas de planning (404) : lue quand même
    en_tetes = [p for m, u, p in session.appels if u.endswith("/users")]
    assert en_tetes == [[("login", "jeanmassiet"), ("login", "hugoauperchoir"), ("login", "usul2000")]]


def test_direct_fini_passe_en_termine(conf, connexion):
    _collecter(conf, connexion, Session(routeur()))
    plus_tard = MAINTENANT + timedelta(hours=2)
    rapport = _collecter(conf, connexion, Session(routeur(directs=None)), plus_tard)
    assert rapport.directs_finis == 1
    statut, fin = connexion.execute("SELECT statut, fin FROM emissions WHERE id = 'twitch:direct:4242'").fetchone()
    assert (statut, fin) == ("terminé", "2027-03-27T12:00:00+01:00")


def test_api_en_panne_n_annule_rien(conf, connexion):
    _collecter(conf, connexion, Session(routeur()))

    def panne(methode, url, params):
        if url.endswith("/schedule"):
            import requests
            raise requests.ConnectionError("panne")
        return routeur()(methode, url, params)

    _collecter(conf, connexion, Session(panne))
    statut = connexion.execute(
        "SELECT statut FROM emissions WHERE id = 'twitch:seg-presidentielle:202703282000'").fetchone()[0]
    assert statut == "annoncé"


def test_sans_identifiants(conf, connexion, monkeypatch):
    monkeypatch.delenv("TWITCH_CLIENT_ID", raising=False)
    monkeypatch.delenv("TWITCH_CLIENT_SECRET", raising=False)
    rapport = twitch.collecter(conf, Session(routeur()), connexion, MAINTENANT)
    assert "TWITCH_CLIENT_ID" in rapport.interrompu


def test_logos_twitch(conf, connexion):
    _collecter(conf, connexion, Session(routeur()))
    assert db.logos(connexion)["BackSeat (Jean Massiet)"].endswith("jeanmassiet-profile_image-300x300.png")


def test_a_l_air_libre_reconnue_a_son_creneau():
    """Direct de Mediapart un jeudi à 19 h : retenu, titre précédé du nom de l'émission."""
    from grille.filtre import FiltrePolitique
    conf = config.charger()
    mediapart = next(c for c in conf.chaines if c.nom == "Mediapart" and c.plateforme == "twitch")
    rapport = twitch.Rapport()
    debut = datetime(2026, 11, 12, 19, 1, tzinfo=PARIS)
    twitch._retenir(rapport, FiltrePolitique(conf), mediapart, "twitch:direct:1", "Trump face à ses promesses",
                    "Just Chatting", debut, None, "en direct")
    (e,) = rapport.retenues
    assert (e["titre"], e["filtre"]) == ("À l'air libre — Trump face à ses promesses", "liste blanche")
