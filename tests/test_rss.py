"""Mesure des flux RSS, à partir d'un extrait réel du flux de TF1info (9 novembre 2026, 17 h 46)."""

from datetime import datetime

import pytest
import requests

from grille import courriel, db, rss
from grille.config import charger
from grille.tv import PARIS
from tests.session_factice import REPONSES, Reponse, Session

MAINTENANT = datetime(2026, 11, 9, 17, 50, tzinfo=PARIS)
TF1INFO = (REPONSES / "rss_tf1info.xml").read_bytes()
ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Essai</title>
<entry><title>Jordan Bardella sera l'invit\xc3\xa9 de BFMTV demain matin</title>
<link href="https://exemple.fr/bardella"/><id>tag:exemple.fr,2026:1</id>
<published>2026-11-09T16:00:00+01:00</published><summary>Face \xc3\xa0 Apolline de Malherbe.</summary></entry>
</feed>"""


class ReponseXml(Reponse):
    def __init__(self, contenu, status_code=200):
        super().__init__(status_code)
        self.content = contenu
        self.text = contenu.decode("utf-8")


def session(*contenus):
    reponses = list(contenus)

    def repondre(methode, url, params):
        r = reponses.pop(0)
        if isinstance(r, Exception):
            raise r
        return ReponseXml(r)
    return Session(repondre)


@pytest.fixture
def conf():
    c = charger()
    c.rss = [{"nom": "TF1info, à la une", "adresse": "https://www.tf1info.fr/feeds/rss-une.xml"}]
    return c


@pytest.fixture
def connexion(tmp_path):
    c = db.ouvrir(tmp_path / "g.sqlite")
    yield c
    c.close()


def test_lire_flux_rss():
    articles = rss.lire_flux(TF1INFO)
    assert len(articles) == 6
    tondelier = articles[3]
    assert tondelier["titre"] == "Présidentielle 2027 : Marine Tondelier invitée du 20H de TF1 ce lundi"
    assert tondelier["publie"] == datetime(2026, 11, 9, 15, 50, 35, tzinfo=PARIS)
    assert tondelier["lien"].startswith("https://www.tf1info.fr/politique/")


def test_lire_flux_atom():
    (a,) = rss.lire_flux(ATOM)
    assert (a["lien"], a["id"]) == ("https://exemple.fr/bardella", "tag:exemple.fr,2026:1")
    assert a["publie"] == datetime(2026, 11, 9, 16, 0, tzinfo=PARIS)


def test_annonce_reperee_une_seule_fois(conf, connexion):
    rapport = rss.collecter(conf, session(TF1INFO), connexion, MAINTENANT)
    assert rapport.flux_lus == 1 and rapport.articles == 6
    # Seule l'annonce de Marine Tondelier : Sophie Marceau n'est pas dans politique.yaml, et
    # « s'inviter » dans un article de santé ne nomme personne.
    (a,) = rapport.nouvelles
    assert a["personnes"] == ["Marine Tondelier"] and "TF1" in a["chaines"] and not a["deja_en_grille"]
    assert a["publie"] == "2026-11-09T15:50:35+01:00" and a["vu_le"] == "2026-11-09T17:50:00+01:00"
    # Revue à la collecte suivante : pas notée deux fois.
    assert rss.collecter(conf, session(TF1INFO), connexion, MAINTENANT.replace(minute=59)).nouvelles == []
    assert len(db.rss_depuis(connexion, MAINTENANT.replace(hour=0))) == 1


def test_deja_en_grille(conf, connexion):
    db.enregistrer_collecte(connexion, [{
        "id": "evenement:202611092000:tv:tf1", "titre": "Le 20h — Marine Tondelier", "debut": "2026-11-09T20:00:00+01:00",
        "fin": "2026-11-09T20:45:00+01:00", "plateforme": "tv", "chaine": "TF1", "categorie": "interview",
        "invites": ["Marine Tondelier"], "cites": [], "resume": "", "lien": [], "statut": "annoncé",
        "filtre": "liste blanche"}], "evenement", set(), MAINTENANT)
    (a,) = rss.collecter(conf, session(TF1INFO), connexion, MAINTENANT).nouvelles
    assert a["deja_en_grille"]


def test_flux_en_panne_et_articles_anciens(conf, connexion):
    conf.rss = conf.rss + [{"nom": "Atom", "adresse": "https://exemple.fr/flux"}]
    rapport = rss.collecter(conf, session(requests.ConnectionError("hors ligne"), ATOM), connexion, MAINTENANT)
    assert rapport.anomalies == ["flux illisible : TF1info, à la une (ConnectionError)"]
    assert [a["personnes"] for a in rapport.nouvelles] == [["Jordan Bardella"]]
    # Plus de 36 heures : ignoré.
    plus_tard = datetime(2026, 11, 11, 9, 0, tzinfo=PARIS)
    assert rss.collecter(conf, session(TF1INFO, ATOM), connexion, plus_tard).articles == 0


def test_email(conf, connexion):
    rss.collecter(conf, session(TF1INFO), connexion, MAINTENANT)
    c = courriel.contenu(connexion, conf, MAINTENANT.replace(hour=23))
    assert c["rss"]["nombre"] == 1 and c["rss"]["inconnues"] == 1
    texte = courriel.texte(c)
    assert "FLUX RSS DES DERNIÈRES 24 H : 1 annonce de passages médias, dont 1 que la grille ignorait" in texte
    assert "NOUVEAU Présidentielle 2027 : Marine Tondelier invitée du 20H de TF1 ce lundi" in texte
    assert "publié 15:50, vu lundi 9 novembre 17:50" in texte
    assert "Marine Tondelier invitée du 20H" in courriel.page_html(c)


CANDIDATURES = [("Public Sénat", "rss_publicsenat.xml"), ("20 Minutes, politique", "rss_20minutes.xml"),
                ("Le Parisien, politique", "rss_leparisien.xml")]


def test_nouveau_candidat_propose(conf, connexion):
    """Teddy Riner (9 novembre 2026) avant son ajout à politique.yaml : sept articles dans trois
    flux le présentent comme candidat ; l'email propose la ligne à copier."""
    conf.candidats = [c for c in conf.candidats if c["nom"] != "Teddy Riner"]
    conf.rss = [{"nom": nom, "adresse": f"https://exemple.fr/{fichier}"} for nom, fichier in CANDIDATURES]
    contenus = [(REPONSES / fichier).read_bytes() for _, fichier in CANDIDATURES]
    rapport = rss.collecter(conf, session(*contenus), connexion, MAINTENANT)
    assert sum(c["nom"] == "Teddy Riner" for c in rapport.candidats) == 7
    assert "Los Angeles" not in {c["nom"] for c in rapport.candidats}
    proposes = courriel.candidats_possibles(connexion, conf, MAINTENANT)
    # Un nom vu dans un seul article (Yannick Jadot, cité par Raphaël Glucksmann) n'est pas proposé.
    assert [c["nom"] for c in proposes] == ["Teddy Riner"]
    riner = proposes[0]
    assert len(riner["articles"]) == 7 and riner["flux"] == [nom for nom, _ in sorted(CANDIDATURES, key=lambda x: x[0])]
    assert riner["ligne"].strip() == ('- {nom: "Teddy Riner", alias: ["Riner"], parti: "", sigle: "", '
                                      'statut: "à vérifier (vu le 9 novembre 2026)"}')
    texte = courriel.texte(courriel.contenu(connexion, conf, MAINTENANT.replace(hour=23)))
    assert "CANDIDATS POSSIBLES À AJOUTER" in texte and "Teddy Riner : 7 articles" in texte
    # Une fois ajouté à politique.yaml, il n'est plus proposé ni noté.
    assert courriel.candidats_possibles(connexion, charger(), MAINTENANT) == []


def test_candidat_deja_connu_pas_note(conf, connexion):
    conf.rss = [{"nom": "Le Parisien, politique", "adresse": "https://exemple.fr/p"}]
    rapport = rss.collecter(conf, session((REPONSES / "rss_leparisien.xml").read_bytes()), connexion, MAINTENANT)
    assert "Teddy Riner" not in {c["nom"] for c in rapport.candidats}



# Titres réels des flux du 9 novembre 2026 (BFMTV, RMC, TF1info, franceinfo, Le Parisien), lus
# par la collecte de 18 h 15 après l'annonce de Teddy Riner.
REACTIONS = [
    ("BFMTV, politique", "Présidentielle 2027: \"Je ne voudrais pas qu'il se détourne de son objectif des JO de "
     "Los Angeles\", réagit Amélie Oudéa-Castéra sur la candidature de Teddy Riner"),
    ("BFMTV, politique", "Teddy Riner candidat à l'élection présidentielle: \"Il porte un message de rassemblement\", "
     "pointe Amélie Oudéa-Castera, ancienne ministre des Sports"),
    ("RMC, politique", "Teddy Riner candidat à la présidentielle 2027: \"Il faudrait qu'il règle ses histoires de "
     "voitures de luxe déjà...\", tacle Daniel Riolo"),
    ("RMC, politique", "Teddy Riner candidat à la présidentielle : \"J'annonce également ma candidature\", "
     "en profite Daniel Riolo"),
    ("TF1info, à la une", "\"Il y a le panache du sportif qui s'exprime\" : l'ex-ministre des Sports Amélie "
     "Oudéa-Castéra réagit sur LCI à la candidature de Teddy Riner"),
    ("franceinfo, politique", "Thierry Breton \"ne ferme pas la porte\" à une candidature pour l'élection "
     "présidentielle en 2027"),
    ("Le Parisien, politique", "Présidentielle 2027 : « On verra », Thierry Breton « ne ferme pas la porte » à "
     "une éventuelle candidature"),
]


def test_commentateurs_d_une_candidature_pas_proposes(conf, connexion):
    """Les personnes qui réagissent à la candidature d'un candidat connu ne sont pas proposées ;
    Thierry Breton, qui « ne ferme pas la porte », l'est."""
    connus, candidats = rss.noms_connus(conf), rss.noms_candidats(conf)
    trouves = {nom for _, titre in REACTIONS
               for nom in rss.candidats_possibles({"titre": titre, "resume": ""}, connus, candidats)}
    assert trouves == {"Thierry Breton"}
    # Notés avant cette règle (base du 9 novembre au soir) : l'email les écarte aussi.
    db.noter_rss_candidats(connexion, [
        {"nom": nom, "id": f"article-{i}", "flux": flux, "titre": titre, "lien": "https://exemple.fr",
         "vu_le": MAINTENANT.isoformat()}
        for i, (flux, titre) in enumerate(REACTIONS)
        for nom in ("Amélie Oudéa-Castéra", "Daniel Riolo", "Thierry Breton") if nom.split()[-1][:5] in titre], MAINTENANT)
    assert [c["nom"] for c in courriel.candidats_possibles(connexion, conf, MAINTENANT)] == ["Thierry Breton"]
