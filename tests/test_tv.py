"""Collecteur télévision, à partir d'un extrait enregistré du guide XMLTV."""

import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from grille import config, db, tv

EXTRAIT = Path(__file__).parent / "reponses" / "xmltv_tnt_extrait.xml"
MAINTENANT = datetime(2027, 3, 15, 10, 0, tzinfo=tv.PARIS)


@pytest.fixture
def conf():
    return config.charger()


@pytest.fixture
def connexion(tmp_path):
    c = db.ouvrir(tmp_path / "grille.sqlite")
    yield c
    c.close()


def _gz(tmp_path, contenu: bytes) -> Path:
    chemin = tmp_path / "guide.xml.gz"
    chemin.write_bytes(gzip.compress(contenu))
    return chemin


@pytest.mark.parametrize(
    "valeur, attendu",
    [
        ("20270315210000 +0100", "2027-03-15T21:00:00+01:00"),
        ("20270615210000 +0200", "2027-06-15T21:00:00+02:00"),
        ("20270615190000 +0000", "2027-06-15T21:00:00+02:00"),
        ("20270315210000", "2027-03-15T21:00:00+01:00"),
    ],
)
def test_lire_date_en_heure_de_paris(valeur, attendu):
    assert tv.lire_date(valeur).isoformat() == attendu


def test_collecte_garde_le_politique_des_8_jours(conf, connexion, tmp_path):
    rapport = tv.collecter(conf, _gz(tmp_path, EXTRAIT.read_bytes()), connexion, MAINTENANT)
    retenues = {e["id"]: e for e in rapport.retenues}
    assert set(retenues) == {
        "tv:France5.fr:202703150930",
        "tv:France2.fr:202703152100",
        "tv:BFMTV.fr:202703151900",
        "tv:LaChaineParlementaire.fr:202703152200",
        "tv:France2.fr:202703160740",
        "tv:France3.fr:202703222010",
    }
    debat = retenues["tv:France2.fr:202703152100"]
    assert debat["titre"] == "Le grand débat — Spécial présidentielle"
    assert debat["debut"] == "2027-03-15T21:00:00+01:00"
    assert (debat["categorie"], debat["filtre"]) == ("débat", "mots-clés")
    assert debat["invites"] == ["Jean-Luc Mélenchon", "Jordan Bardella"]
    assert debat["lien"] == ["https://www.france.tv/france-2/direct.html"]
    assert retenues["tv:France5.fr:202703150930"]["statut"] == "en direct"
    assert retenues["tv:France2.fr:202703160740"]["filtre"] == "liste blanche"
    assert retenues["tv:France2.fr:202703160740"]["categorie"] == "interview"
    assert retenues["tv:France3.fr:202703222010"]["categorie"] == "meeting"
    assert retenues["tv:LaChaineParlementaire.fr:202703152200"]["filtre"] == "liste blanche"
    assert rapport.chaines_absentes == ["CNews", "LCI", "M6", "franceinfo"]
    fin = MAINTENANT + timedelta(days=8)
    assert [e["id"] for e in db.lister(connexion, MAINTENANT, fin)][0] == "tv:France5.fr:202703150930"


def test_seconde_collecte_met_a_jour_et_annule(conf, connexion, tmp_path):
    tv.collecter(conf, _gz(tmp_path, EXTRAIT.read_bytes()), connexion, MAINTENANT)
    modifie = (
        EXTRAIT.read_text(encoding="utf-8")
        .replace("Le grand débat", "Le débat décisif")
        .replace('channel="BFMTV.fr"', 'channel="Gulli.fr"')  # BFM Politique disparaît du guide
        .replace('<programme start="20270322201000 +0100" stop="20270322220000 +0100" channel="France3.fr">',
                 '<programme start="20270322201000 +0100" stop="20270322220000 +0100" channel="M6.fr">')
    )
    rapport = tv.collecter(conf, _gz(tmp_path, modifie.encode("utf-8")), connexion, MAINTENANT + timedelta(hours=1))

    lignes = dict(connexion.execute("SELECT id, statut FROM emissions"))
    titre = connexion.execute("SELECT titre FROM emissions WHERE id = 'tv:France2.fr:202703152100'").fetchone()[0]
    assert titre.startswith("Le débat décisif")  # même ligne, titre mis à jour
    # BFMTV n'apparaît plus du tout dans le guide : panne de source, rien n'est annulé.
    assert lignes["tv:BFMTV.fr:202703151900"] == "annoncé"
    # France 3 est toujours dans le guide mais l'émission a disparu : annulée.
    assert lignes["tv:France3.fr:202703222010"] == "annulé"
    assert rapport.annulees == 1


def test_guide_non_compresse_accepte(conf, connexion, tmp_path):
    chemin = tmp_path / "guide.xml"
    shutil.copy(EXTRAIT, chemin)
    assert len(tv.collecter(conf, chemin, connexion, MAINTENANT).retenues) == 6


def test_programmes_de_nuit_masques(conf, connexion, tmp_path):
    nuit = EXTRAIT.read_text(encoding="utf-8").replace(
        '<programme start="20270316074000 +0100" stop="20270316080000 +0100" channel="France2.fr">',
        '<programme start="20270316020000 +0100" stop="20270316030000 +0100" channel="France2.fr">',
    )
    rapport = tv.collecter(conf, _gz(tmp_path, nuit.encode("utf-8")), connexion, MAINTENANT)
    assert "tv:France2.fr:202703160200" not in {e["id"] for e in rapport.retenues}
    assert rapport.masques >= 1


def test_chercher_explique_le_verdict(conf, tmp_path):
    resultats = tv.chercher(conf, _gz(tmp_path, EXTRAIT.read_bytes()), "débat", MAINTENANT)
    verdicts = {(r["chaine"], r["titre"]): r["verdict"] for r in resultats}
    assert verdicts[("France 2", "Le grand débat")].startswith("RETENUE")
    assert verdicts[("Gulli.fr", "Débat junior")] == "chaîne non configurée (Gulli.fr)"
    assert ("France 2", "Débat matinal") not in verdicts  # terminé avant « maintenant »


def test_logo_du_guide(conf, connexion, tmp_path):
    tv.collecter(conf, _gz(tmp_path, EXTRAIT.read_bytes()), connexion, MAINTENANT)
    assert db.logos(connexion) == {"France 2": "https://example.org/logos/france2.png"}


def _guide_lci(titre, description=""):
    desc = f"<desc lang=\"fr\">{description}</desc>" if description else ""
    return (f'<?xml version="1.0" encoding="UTF-8"?><tv><channel id="LCI.fr"><display-name>LCI</display-name></channel>'
            f'<programme start="20261025110000 +0100" stop="20261025120000 +0100" channel="LCI.fr">'
            f'<title lang="fr">{titre}</title>{desc}</programme></tv>').encode()


def test_description_perdue_par_le_guide(conf, connexion, tmp_path):
    """Comme « Objectif 2027 dimanche » (LCI) le 22 octobre 2026 : retenu grâce à sa description,
    puis annulé quand le guide l'a perdue. Même programme, même heure : il reste."""
    avant = datetime(2026, 10, 21, 10, 0, tzinfo=tv.PARIS)
    tv.collecter(conf, _gz(tmp_path, _guide_lci("Le grand dossier week-end", "Un nouveau rendez-vous hebdomadaire avec "
                 "des personnalités politiques, avec toujours en ligne de mire les élections présidentielles.")),
                 connexion, avant)
    rapport = tv.collecter(conf, _gz(tmp_path, _guide_lci("Le grand dossier week-end")), connexion, avant + timedelta(hours=1))
    assert rapport.annulees == 0
    [e] = db.lister(connexion, datetime(2026, 10, 25, tzinfo=tv.PARIS), datetime(2026, 10, 26, tzinfo=tv.PARIS))
    assert e["titre"] == "Le grand dossier week-end" and "présidentielles" in e["resume"]
    # Un autre programme à la même heure, lui, annule l'émission.
    rapport = tv.collecter(conf, _gz(tmp_path, _guide_lci("Histoires criminelles")), connexion, avant + timedelta(hours=2))
    assert rapport.annulees == 1
