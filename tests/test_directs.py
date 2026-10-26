"""Sujet du jour des émissions en cours (grille/directs.py), à partir d'une page enregistrée de france.tv."""

from datetime import datetime
from pathlib import Path

import pytest
import requests

from grille import config, db, directs
from grille.tv import PARIS
from tests.session_factice import REPONSES, Reponse, Session

PAGE = (REPONSES / "francetv_direct_france5.html").read_text(encoding="utf-8")
PENDANT = datetime(2026, 10, 23, 19, 21, tzinfo=PARIS)


def page_html(texte, statut=200):
    r = Reponse(statut)
    r.text = texte
    return r


@pytest.fixture
def conf():
    return config.charger()


@pytest.fixture
def connexion(tmp_path):
    c = db.ouvrir(tmp_path / "g.sqlite")
    yield c
    c.close()


def routeur(france5=PAGE):
    def repondre(methode, url, params):
        if url == "https://www.france.tv/france-5/direct.html":
            return page_html(france5)
        if url == "https://www.france.tv/france-2/direct.html":
            raise requests.ConnectionError("délai dépassé")
        return page_html("<html>rien</html>")
    return repondre


def test_lire_la_page_du_direct():
    e = directs.lire_page(PAGE)
    assert e["emission"] == "C à vous"
    assert e["sujet"] == "Invités : Alexandre Bompard, Noémie Schulz, Ludovic Vigogne, Julia Martin"  # sans « S18 - »
    assert e["debut"].isoformat() == "2026-10-23T18:57:44+02:00" and e["fin"].isoformat() == "2026-10-23T20:02:44+02:00"
    assert "Emmanuel Macron au cœur du dispositif" in e["description"]
    assert directs.lire_page("<html><h2>Autre chose</h2></html>") is None


def test_emission_politique_ajoutee_pendant_sa_diffusion(conf, connexion):
    rapport = directs.collecter(conf, Session(routeur()), connexion, PENDANT)
    assert rapport.pages_lues == 1 and not rapport.interrompu  # France 5 lue
    assert rapport.illisibles == ["France 3"]  # page sans émission décrite : pas d'alerte
    assert rapport.anomalies == ["direct illisible : France 2 (délai dépassé)"]
    [e] = rapport.retenues
    assert e["id"] == "direct:france-5:202610231857"
    assert e["titre"] == "C à vous — Invités : Alexandre Bompard, Noémie Schulz, Ludovic Vigogne, Julia Martin"
    assert e["statut"] == "en direct" and e["chaine"] == "France 5"
    assert "Emmanuel Macron" in e["cites"]  # cité dans le résumé, pas sur le plateau
    assert e["lien"] == ["https://www.france.tv/france-5/direct.html"]
    assert [x["id"] for x in db.lister(connexion, PENDANT, PENDANT)] == ["direct:france-5:202610231857"]
    # Collecte suivante du guide télé : l'émission déjà commencée n'est pas « annulée ».
    db.enregistrer_collecte(connexion, [], "tv", {"France 5"}, PENDANT)
    assert len(db.lister(connexion, PENDANT, PENDANT)) == 1


def test_sujet_non_politique_ou_emission_terminee(conf, connexion):
    meteo = PAGE.replace("Emmanuel Macron", "le préfet").replace("journaliste politique", "journaliste")
    assert directs.collecter(conf, Session(routeur(meteo)), connexion, PENDANT).retenues == []
    apres = datetime(2026, 10, 23, 20, 10, tzinfo=PARIS)
    assert directs.collecter(conf, Session(routeur()), connexion, apres).retenues == []


def test_toutes_les_pages_illisibles(conf, connexion):
    rapport = directs.collecter(conf, Session(routeur("<html>nouveau format</html>")), connexion, PENDANT)
    assert rapport.interrompu.startswith("aucune page du direct lisible")


def test_homonyme_ecarte(conf):
    """Alexandre Bompard (PDG de Carrefour), invité de « C à vous », n'est pas Manuel Bompard (LFI)."""
    from grille.filtre import FiltrePolitique
    e = directs.lire_page(PAGE)
    chaines = {c.nom: c for c in conf.chaines}
    d = FiltrePolitique(conf).decider(chaines["France 5"], e["emission"], e["description"], sous_titre=e["sujet"])
    assert "Manuel Bompard" not in d.invites + d.cites


def test_pas_de_doublon_avec_le_guide(conf, connexion):
    guide = {"id": "tv:France5.fr:202610231855", "titre": "C à vous", "debut": "2026-10-23T18:55:00+02:00",
             "fin": "2026-10-23T20:00:00+02:00", "plateforme": "tv", "chaine": "France 5", "categorie": "interview",
             "invites": [], "lien": [], "statut": "en direct", "filtre": "liste blanche"}
    db.enregistrer_collecte(connexion, [guide], "tv", set(), PENDANT)
    assert directs.collecter(conf, Session(routeur()), connexion, PENDANT).retenues == []


def test_le_sujet_du_22_octobre_aurait_ete_retenu(conf):
    """« C ce soir » du 22 octobre : « LFI - gouvernement : la stratégie de la tension ? »."""
    from grille.filtre import FiltrePolitique
    chaines = {c.nom: c for c in conf.chaines}
    d = FiltrePolitique(conf).decider(chaines["France 5"], "C ce soir", "", sous_titre="LFI - gouvernement : la stratégie de la tension ?")
    assert d is not None and d.filtre == "mots-clés"
