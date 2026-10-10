"""Invités annoncés, à partir d'un extrait enregistré de la liste des communiqués de francetvpro.fr."""

from datetime import date, datetime

import pytest
import requests

from grille import affichage, annonces, config, db
from grille.acces import FRANCETVPRO
from grille.filtre import FiltrePolitique
from grille.tv import PARIS
from tests.session_factice import REPONSES

PAGE = (REPONSES / "francetvpro_liste.html").read_text(encoding="utf-8")
MAINTENANT = datetime(2026, 10, 10, 18, 41, tzinfo=PARIS)


class ReponseHtml:
    def __init__(self, texte, statut=200):
        self.text, self.status_code = texte, statut

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class SessionHtml:
    def __init__(self, pages):
        self.pages, self.appels = pages, []

    def get(self, url, params=None, **kwargs):
        assert url == FRANCETVPRO
        self.appels.append(params["page"])
        page = self.pages.get(params["page"], "<html>fin de liste</html>")
        if isinstance(page, Exception):
            raise page
        return ReponseHtml(page)


@pytest.fixture
def conf():
    return config.charger()


def test_lire_page(conf):
    cartes, liste = annonces.lire_page(PAGE, MAINTENANT.date(), FiltrePolitique(conf))
    assert cartes == 4
    # La programmation guyanaise (passée) et « Les yeux dans les vieux » (sans invité) sont écartées.
    assert [(a.id, a.jour, a.heure, a.invites) for a in liste] == [
        ("78939603", "2026-10-11", "18:00", ["Yannick Jadot"]),
        ("78939602", "2026-10-11", "13:20", ["Roland Lescure"]),
    ]
    franc_jeu = liste[1]
    assert franc_jeu.titre == "FRANC-JEU — Roland Lescure — Invité de Benjamin Duhamel"
    assert franc_jeu.url == "https://www.francetvpro.fr/contenu-de-presse/78939602"


@pytest.mark.parametrize("texte, attendu", [
    ("Dimanche 11 octobre à 13h20 sur France 2, France Inter et france.tv", (date(2026, 10, 11), "13:20")),
    ("Dimanche 11 octobre en direct sur franceinfo canal 16 à 18.00", (date(2026, 10, 11), "18:00")),
    ("Samedi 10 octobre 2026 à 13h05", (date(2026, 10, 10), "13:05")),
    ("Vendredi 9 et samedi 10 octobre", (date(2026, 10, 10), "")),
    ("Jeudi 7 janvier à 21h", (date(2027, 1, 7), "21:00")),  # janvier suivant
    ("Prochainement sur France 5", None),
])
def test_lire_date(texte, attendu):
    assert annonces.lire_date(texte, date(2026, 10, 10)) == attendu


def test_invites(conf):
    filtre = FiltrePolitique(conf)
    assert annonces.invites(["L'heure de vérité", "Jordan Bardella et Marine Tondelier"], "", filtre) == [
        "Jordan Bardella", "Marine Tondelier"]
    assert annonces.invites(["C ce soir avec Benjamin Duhamel"], "", filtre) == []
    # Personnalité suivie citée dans le résumé, même sans « reçoit ».
    assert "Marion Maréchal" in annonces.invites(["FRANC-JEU", "Gabriel Attal"], "En fin d'émission, débat avec "
                                                 "Marion Maréchal.", filtre)


def test_collecte_et_affichage(conf, tmp_path):
    connexion = db.ouvrir(tmp_path / "g.sqlite")
    session = SessionHtml({0: PAGE, 2: requests.ConnectionError("coupure")})
    rapport = annonces.collecter(conf, session, connexion, MAINTENANT)
    assert session.appels == [0, 1, 2, 3]
    assert rapport.pages_lues == 3 and rapport.cartes == 4 and not rapport.interrompu
    assert rapport.anomalies == ["page 3 des communiqués illisible (coupure)"]
    franc_jeu = {"id": "tv:France2.fr:202610111320", "titre": "Franc-jeu", "debut": "2026-10-11T13:20:00+02:00",
                 "fin": "2026-10-11T14:05:00+02:00", "plateforme": "tv", "chaine": "France 2", "categorie": "analyse",
                 "invites": [], "lien": [], "statut": "annoncé", "filtre": "liste blanche"}
    rediffusion = dict(franc_jeu, id="tv:x", debut="2026-10-11T23:20:00+02:00", fin=None)
    db.enregistrer_collecte(connexion, [franc_jeu, rediffusion], "tv", set(), MAINTENANT)
    (premiere, seconde) = affichage.emissions(connexion, MAINTENANT, datetime(2026, 10, 12, tzinfo=PARIS))
    assert premiere["invites"] == ["Roland Lescure"]
    assert seconde["invites"] == []  # autre heure : pas la même diffusion
    # La base n'est pas modifiée : l'annonce s'applique à l'affichage.
    assert db.lister(connexion, MAINTENANT, datetime(2026, 10, 12, tzinfo=PARIS))[0]["invites"] == []
    connexion.close()


def test_structure_changee(conf, tmp_path):
    connexion = db.ouvrir(tmp_path / "g.sqlite")
    rapport = annonces.collecter(conf, SessionHtml({}), connexion, MAINTENANT)
    assert rapport.interrompu == "aucun communiqué reconnu : la page a sans doute changé de structure"
    connexion.close()
