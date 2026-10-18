"""Événements ajoutés à la main (config/evenements.yaml)."""

import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from grille import affichage, config, db, evenements
from grille.tv import PARIS

MAINTENANT = datetime(2026, 10, 18, 14, 0, tzinfo=PARIS)
EVENEMENTS = """\
evenements:
  - titre: "Allocution d'Emmanuel Macron"
    debut: "2026-10-18 20:00"
    duree: 20
    chaines: ["TF1", "France 2", "franceinfo", "franceinfo (radio)", "Chaîne inconnue"]
    resume: "Le président de la République s'adresse aux Français."
  - {titre: "Sans heure lisible", debut: "ce soir", chaines: ["TF1"]}
  - {titre: "Sans chaîne", debut: "2026-10-18 21:00"}
"""


@pytest.fixture
def conf(tmp_path):
    for f in ("chaines.yaml", "politique.yaml"):
        shutil.copy(Path(config.DOSSIER_CONFIG) / f, tmp_path / f)
    (tmp_path / "evenements.yaml").write_text(EVENEMENTS, encoding="utf-8")
    return config.charger(tmp_path)


@pytest.fixture
def connexion(tmp_path):
    c = db.ouvrir(tmp_path / "grille.sqlite")
    yield c
    c.close()


def test_une_carte_avec_un_lien_par_chaine(conf, connexion):
    assert conf.anomalies == ["evenements.yaml, événement n° 3 : « titre », « debut » et « chaines » sont obligatoires"]
    rapport = evenements.collecter(conf, connexion, MAINTENANT)
    assert sorted(rapport.anomalies) == [
        "« Allocution d'Emmanuel Macron » : chaîne inconnue « Chaîne inconnue » (nom de chaines.yaml)",
        "« Sans heure lisible » : heure illisible « ce soir » (écrire 2026-10-18 20:00)",
    ]
    assert [(e["chaine"], e["plateforme"]) for e in rapport.retenues] == [
        ("TF1", "tv"), ("France 2", "tv"), ("franceinfo", "tv"), ("franceinfo", "radio")]
    tf1 = rapport.retenues[0]
    assert tf1["debut"] == "2026-10-18T20:00:00+02:00" and tf1["fin"] == "2026-10-18T20:20:00+02:00"
    assert tf1["invites"] == ["Emmanuel Macron"] and tf1["categorie"] == "meeting"
    assert tf1["lien"] == ["https://www.tf1.fr/tf1/direct"] and tf1["statut"] == "annoncé"
    # La fusion n'en fait qu'une carte, avec le direct de chaque chaîne (franceinfo télé et radio compris).
    [carte] = affichage.emissions(connexion, MAINTENANT, MAINTENANT + timedelta(days=1))
    assert carte["plateforme"] == "tv" and len(carte["lien"]) == 4


def test_jamais_annule_par_le_guide_tele_mais_retire_du_fichier(conf, connexion, tmp_path):
    evenements.collecter(conf, connexion, MAINTENANT)
    # Le guide télé ne connaît pas l'allocution : sa collecte ne l'annule pas.
    db.enregistrer_collecte(connexion, [], "tv", {"TF1", "France 2"}, MAINTENANT)
    assert len(db.lister(connexion, MAINTENANT, MAINTENANT + timedelta(days=1))) == 4
    # Retiré du fichier avant sa date : annulé.
    (tmp_path / "evenements.yaml").write_text("evenements: []\n", encoding="utf-8")
    rapport = evenements.collecter(config.charger(tmp_path), connexion, MAINTENANT)
    assert rapport.annulees == 4
    assert {s for (s,) in connexion.execute("SELECT statut FROM emissions")} == {"annulé"}
