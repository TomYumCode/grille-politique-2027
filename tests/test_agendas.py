"""Agendas des partis, à partir d'extraits enregistrés des pages du RN et de l'UPR."""

from datetime import date, datetime

import pytest
import requests

from grille import affichage, agendas, config, db
from grille.tv import PARIS
from tests.session_factice import REPONSES

RN = (REPONSES / "agenda_rn.html").read_text(encoding="utf-8")
UPR = (REPONSES / "agenda_upr.html").read_text(encoding="utf-8")
MAINTENANT = datetime(2026, 10, 11, 2, 11, tzinfo=PARIS)
FIN = datetime(2026, 10, 19, tzinfo=PARIS)


class ReponseHtml:
    def __init__(self, texte, statut=200):
        self.text, self.status_code, self.encoding = texte, statut, "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class SessionHtml:
    def __init__(self, pages):
        self.pages = pages

    def get(self, url, **kwargs):
        page = self.pages[url]
        if isinstance(page, Exception):
            raise page
        return ReponseHtml(page)


@pytest.fixture
def conf():
    return config.charger()


@pytest.fixture
def connexion(tmp_path):
    c = db.ouvrir(tmp_path / "g.sqlite")
    yield c
    c.close()


def test_lire_rn():
    rdv = agendas.lire_rn(RN, "https://rassemblementnational.fr/agenda", date(2026, 10, 11))
    assert [(r.titre, r.debut.isoformat(), r.media) for r in rdv] == [
        ("Andréa Kotarac sur BFM", "2026-10-11T17:00:00+02:00", True),
        ("Sébastien Chenu sur LCI", "2026-10-11T18:00:00+02:00", True),
        ("Jean-Philippe Tanguy sur Paris Première", "2026-10-12T20:45:00+02:00", True),
        ("Jean-Philippe Tanguy sur RTL", "2026-10-13T07:40:00+02:00", True),
    ]
    assert rdv[0].description == "Andréa Kotarac sera l'invité de BFMTV le dimanche 11 octobre 2026 à 17h."


def test_lire_upr():
    rdv = agendas.lire_upr(UPR, "https://upr.fr/agenda", date(2026, 10, 11))
    assert len(rdv) == 3
    asselineau = rdv[2]
    assert asselineau.titre == "Réunion publique de François Asselineau à Villefagnan (Charente)"
    assert (asselineau.debut.isoformat(), asselineau.fin.isoformat()) == (
        "2026-10-18T15:00:00+02:00", "2026-10-18T18:00:00+02:00")
    assert asselineau.lien == "https://upr.fr/agenda/reunion-publique-de-francois-asselineau-a-villefagnan"


def test_collecte(conf, connexion):
    session = SessionHtml({"https://rassemblementnational.fr/agenda": RN, "https://upr.fr/agenda": UPR})
    rapport = agendas.collecter(conf, session, connexion, MAINTENANT)
    assert rapport.agendas_lus == 2 and rapport.rendez_vous == 7 and not rapport.interrompu
    par_titre = {e["titre"]: e for e in rapport.retenues}
    # Les réunions locales de délégation, sans personnalité suivie, sont écartées.
    assert set(par_titre) == {"Andréa Kotarac sur BFM", "Sébastien Chenu sur LCI",
                              "Jean-Philippe Tanguy sur Paris Première", "Jean-Philippe Tanguy sur RTL",
                              "Réunion publique de François Asselineau à Villefagnan (Charente)"}
    bfm = par_titre["Andréa Kotarac sur BFM"]
    assert (bfm["chaine"], bfm["plateforme"], bfm["categorie"], bfm["invites"]) == (
        "BFMTV", "web", "interview", ["Andréa Kotarac"])
    assert bfm["lien"] == ["https://www.bfmtv.com/en-direct/"]
    assert par_titre["Jean-Philippe Tanguy sur Paris Première"]["chaine"] == "Paris Première"
    assert par_titre["Jean-Philippe Tanguy sur RTL"]["chaine"] == "RTL"  # radio suivie sur YouTube
    upr = par_titre["Réunion publique de François Asselineau à Villefagnan (Charente)"]
    assert (upr["chaine"], upr["categorie"], upr["invites"]) == ("UPR", "meeting", ["François Asselineau"])


def test_rattachement_a_l_emission(conf, connexion):
    session = SessionHtml({"https://rassemblementnational.fr/agenda": RN, "https://upr.fr/agenda": UPR})
    agendas.collecter(conf, session, connexion, MAINTENANT)
    emission_bfm = {"id": "tv:BFMTV.fr:202610111700", "titre": "BFM Politique", "debut": "2026-10-11T16:55:00+02:00",
                    "fin": "2026-10-11T18:00:00+02:00", "plateforme": "tv", "chaine": "BFMTV", "categorie": "interview",
                    "invites": [], "lien": ["https://www.bfmtv.com/en-direct/"], "statut": "annoncé",
                    "filtre": "liste blanche"}
    db.enregistrer_collecte(connexion, [emission_bfm], "tv", set(), MAINTENANT)
    titres = {e["titre"]: e for e in affichage.emissions(connexion, MAINTENANT, FIN)}
    assert titres["BFM Politique"]["invites"] == ["Andréa Kotarac"]
    assert "Andréa Kotarac sur BFM" not in titres  # rattaché, pas affiché à part
    assert "Sébastien Chenu sur LCI" in titres  # aucune émission LCI à 18 h dans la grille


def test_agenda_illisible(conf, connexion):
    session = SessionHtml({"https://rassemblementnational.fr/agenda": "<html>travaux</html>",
                           "https://upr.fr/agenda": requests.ConnectionError("coupure")})
    rapport = agendas.collecter(conf, session, connexion, MAINTENANT)
    assert rapport.interrompu.startswith("aucun agenda lisible : agenda illisible : Rassemblement National")
