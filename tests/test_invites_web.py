"""Invité cherché sur le web par Claude, à partir de réponses de l'API (format documenté)."""

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from grille import affichage, db, invites_web
from grille.config import charger
from grille.tv import PARIS
from tests.session_factice import charger as charger_reponse

REPONSES = charger_reponse("claude_invite_grand_oral.json")
MAINTENANT = datetime(2026, 11, 8, 18, 5, tzinfo=PARIS)
GRAND_ORAL = {"id": "tv:BFMTV.fr:202611081800", "titre": "Le grand oral 2027", "debut": "2026-11-08T18:00:00+01:00",
              "fin": "2026-11-08T19:00:00+01:00", "plateforme": "tv", "chaine": "BFMTV", "categorie": "interview",
              "invites": [], "cites": [], "resume": "", "lien": ["https://www.bfmtv.com/en-direct/"],
              "statut": "en direct", "filtre": "liste blanche"}


class Bloc(dict):
    def to_dict(self):
        return dict(self)


def reponse(cle, **changes):
    r = dict(REPONSES[cle], **changes)
    usage = r["usage"]
    return SimpleNamespace(content=[Bloc(b) for b in r["content"]], stop_reason=r["stop_reason"],
                           usage=SimpleNamespace(input_tokens=usage["input_tokens"],
                                                 output_tokens=usage["output_tokens"],
                                                 server_tool_use=SimpleNamespace(**usage["server_tool_use"])))


class Client:
    """Faux client de l'API : rend les réponses prévues et garde les questions posées."""

    def __init__(self, *reponses):
        self.reponses = list(reponses)
        self.appels = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.appels.append(kwargs)
        return self.reponses.pop(0)


@pytest.fixture
def conf():
    c = charger()
    c.recherche = dict(c.recherche, actif=True, recherches_par_jour=12)
    return c


@pytest.fixture
def connexion(tmp_path):
    c = db.ouvrir(tmp_path / "g.sqlite")
    db.enregistrer_collecte(c, [GRAND_ORAL], "tv", set(), MAINTENANT)
    yield c
    c.close()


def test_invite_trouve_et_affiche(conf, connexion):
    client = Client(reponse("trouve"))
    rapport = invites_web.collecter(conf, connexion, MAINTENANT, client=client)
    assert rapport.trouvees == [("Le grand oral 2027", ["Raphaël Glucksmann"])]
    appel = client.appels[0]
    assert appel["model"] == "claude-opus-5-5" and appel["tools"][0]["type"] == "web_search_20260209"
    assert appel["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in appel["betas"]
    assert "BFMTV (télévision)" in appel["messages"][0]["content"]
    assert "dimanche 8 novembre 2026, de 18:00 à 19:00" in appel["messages"][0]["content"]
    # Appliqué à l'affichage, jamais dans la table des émissions.
    (e,) = affichage.emissions(connexion, MAINTENANT, MAINTENANT)
    assert e["invites"] == ["Raphaël Glucksmann"]
    assert json.loads(connexion.execute("SELECT invites FROM emissions").fetchone()[0]) == []
    # Invité connu : plus de question à la collecte suivante.
    assert invites_web.collecter(conf, connexion, MAINTENANT.replace(minute=20), client=Client()).cherchees == 0


def test_source_absente_des_resultats(conf, connexion):
    contenu = [dict(b) for b in REPONSES["trouve"]["content"]]
    contenu[-1]["text"] = contenu[-1]["text"].replace("bfmtv.com/politique", "exemple.fr/invente")
    rapport = invites_web.collecter(conf, connexion, MAINTENANT, client=Client(reponse("trouve", content=contenu)))
    assert rapport.trouvees == [] and "sans page de résultat" in rapport.anomalies[0]


def test_nom_inconnu_signale_pas_ajoute(conf, connexion):
    contenu = [dict(b) for b in REPONSES["trouve"]["content"]]
    contenu[-1]["text"] = contenu[-1]["text"].replace("Raphaël Glucksmann", "Jeanne Inconnue")
    rapport = invites_web.collecter(conf, connexion, MAINTENANT, client=Client(reponse("trouve", content=contenu)))
    assert rapport.trouvees == [] and rapport.inconnus == ["Jeanne Inconnue (« Le grand oral 2027 », BFMTV)"]
    assert db.inconnus_recents(connexion, MAINTENANT) == ["Jeanne Inconnue (« Le grand oral 2027 »)"]


def test_deux_essais_au_plus_et_fenetre(conf, connexion):
    client = Client(reponse("rien"), reponse("rien"))
    assert invites_web.collecter(conf, connexion, MAINTENANT, client=client).cherchees == 1
    # Trop tôt pour un second essai (moins de 15 minutes).
    assert invites_web.collecter(conf, connexion, MAINTENANT.replace(minute=10), client=client).cherchees == 0
    assert invites_web.collecter(conf, connexion, MAINTENANT.replace(minute=25), client=client).cherchees == 1
    assert invites_web.collecter(conf, connexion, MAINTENANT.replace(minute=29), client=Client()).cherchees == 0
    # Plus de 30 minutes après le début : on ne cherche plus.
    autre = dict(GRAND_ORAL, id="tv:BFMTV.fr:x", titre="Face à face", debut="2026-11-08T17:00:00+01:00")
    db.enregistrer_collecte(connexion, [autre], "tv", set(), MAINTENANT)
    assert invites_web.collecter(conf, connexion, MAINTENANT, client=Client()).cherchees == 0


def test_plafond_par_jour(conf, connexion):
    conf.recherche["recherches_par_jour"] = 0
    rapport = invites_web.collecter(conf, connexion, MAINTENANT, client=Client())
    assert rapport.plafond_atteint and rapport.cherchees == 0


def test_pas_une_emission_a_invite(conf):
    documentaire = dict(GRAND_ORAL, titre="Un monde en doc — Campagne présidentielle", filtre="mots-clés",
                        categorie="analyse")
    assert not invites_web.emission_a_invite(documentaire, conf)
    assert invites_web.emission_a_invite(dict(documentaire, titre="L'invité RTL de 7h40", plateforme="radio"), conf)


def test_modele_moins_cher():
    assert invites_web.outil_recherche("claude-haiku-5-5")["type"] == "web_search_20250305"


def test_recherche_arretee(conf, connexion):
    conf.recherche["actif"] = False
    assert invites_web.collecter(conf, connexion, MAINTENANT, client=Client()).interrompu
