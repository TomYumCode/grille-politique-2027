"""Page web : génération depuis la base."""

import json
import re
from datetime import datetime, timedelta

import pytest

from grille import config, db, page
from grille.tv import PARIS

MAINTENANT = datetime(2027, 3, 15, 10, 0, tzinfo=PARIS)


def _emission(id_, debut, **autres):
    return {"id": id_, "titre": "Titre", "debut": debut.isoformat(), "fin": (debut + timedelta(hours=1)).isoformat(),
            "plateforme": "tv", "chaine": "France 2", "categorie": "débat", "invites": [], "lien": [],
            "statut": "annoncé", "filtre": "mots-clés", **autres}


@pytest.fixture
def connexion(tmp_path):
    c = db.ouvrir(tmp_path / "g.sqlite")
    yield c
    c.close()


def _donnees_de(index):
    contenu = re.search(r'<script id="donnees" type="application/json">(.*?)</script>', index.read_text(encoding="utf-8"), re.S)
    return json.loads(contenu.group(1))


def test_page_generee_avec_les_emissions_du_jour_et_de_la_semaine(connexion, tmp_path):
    emissions = [
        _emission("tv:matin", MAINTENANT - timedelta(hours=3)),  # passée mais d'aujourd'hui : gardée
        _emission("tv:soir", MAINTENANT + timedelta(hours=11), invites=["Raphaël Glucksmann"], titre="Débat </script> piégé"),
        _emission("tv:j7", MAINTENANT + timedelta(days=7)),
        _emission("tv:j8", MAINTENANT + timedelta(days=8)),  # au-delà de l'horizon
        _emission("tv:hier", MAINTENANT - timedelta(days=1)),
    ]
    db.enregistrer_collecte(connexion, emissions, "tv", set(), MAINTENANT)
    connexion.execute("UPDATE emissions SET statut = 'annulé' WHERE id = 'tv:j7'")
    index = page.generer(connexion, config.charger(), MAINTENANT, tmp_path / "site")

    donnees = _donnees_de(index)
    assert [e["id"] for e in donnees["emissions"]] == ["tv:matin", "tv:soir"]
    assert donnees["jours"][0] == "2027-03-15" and len(donnees["jours"]) == 8
    # Tous les candidats suivis sont proposés, même sans émission (Marine Tondelier).
    candidats = {c["nom"]: c["emissions"] for c in donnees["candidats"]}
    assert candidats["Raphaël Glucksmann"] == 1 and candidats["Marine Tondelier"] == 0
    assert len(candidats) == len(config.charger().candidats)
    assert donnees["emissions"][1]["titre"] == "Débat </script> piégé"
    for fichier in ("app.js", "style.css", "sw.js", "manifest.webmanifest", "icone-180.png", "icone-512.png", "robots.txt",
                    "sources.html"):
        assert (tmp_path / "site" / fichier).exists()


def test_manifeste_et_service_worker_coherents(tmp_path):
    manifeste = json.loads((page.MODELE / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifeste["display"] == "standalone"
    icones = {i["src"] for i in manifeste["icons"]}
    sw = (page.MODELE / "sw.js").read_text(encoding="utf-8")
    for icone in icones | {"index.html", "sources.html", "app.js", "style.css"}:
        assert (page.MODELE / icone).exists()
        assert f'"{icone}"' in sw  # mis en cache pour le mode hors connexion


def test_logos_de_la_base_et_de_la_configuration(connexion, tmp_path):
    db.enregistrer_collecte(connexion, [_emission("tv:a", MAINTENANT + timedelta(hours=2)),
                                        _emission("tv:b", MAINTENANT + timedelta(hours=3), chaine="BFMTV")],
                            "tv", set(), MAINTENANT)
    db.noter_logos(connexion, {"France 2": "https://source/france2.png", "BFMTV": "", "TF1": "https://source/tf1.png"},
                   MAINTENANT)
    conf = config.charger()
    conf.chaines = [c if c.nom != "BFMTV" else type(c)(**{**c.__dict__, "logo": "https://moi/bfm.png"})
                    for c in conf.chaines]
    donnees = _donnees_de(page.generer(connexion, conf, MAINTENANT, tmp_path / "site"))
    # TF1 n'a pas d'émission : son logo n'est pas embarqué ; BFMTV prend le logo imposé.
    assert donnees["logos"] == {"France 2": "https://source/france2.png", "BFMTV": "https://moi/bfm.png"}


def test_version_legere_pour_les_notifications(connexion, tmp_path):
    """notifications.json : ce que relit le service de notifications, sans liens ni résumés."""
    debut = MAINTENANT + timedelta(hours=2)
    db.enregistrer_collecte(connexion, [_emission("tv:soir", debut, invites=["Raphaël Glucksmann"],
                                                  lien=["https://www.france.tv/france-2/direct.html"])],
                            "tv", set(), MAINTENANT)
    index = page.generer(connexion, config.charger(), MAINTENANT, tmp_path / "site")
    legere = json.loads((tmp_path / "site" / "notifications.json").read_text(encoding="utf-8"))
    [e] = legere["emissions"]
    assert set(e) == set(page.CHAMPS_NOTIFICATIONS)
    assert e["id"] == "tv:soir" and e["invites"] == ["Raphaël Glucksmann"] and "lien" not in e
    assert legere["genere_le"] == _donnees_de(index)["genere_le"]
    # Sans adresse de service (config/notifications.yaml vide), la page ne propose pas les notifications.
    assert _donnees_de(index)["notifications"] == config.charger().notifications


def test_adresse_du_service_de_notifications(tmp_path):
    for f in ("chaines.yaml", "politique.yaml"):
        (tmp_path / f).write_text((config.DOSSIER_CONFIG / f).read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "notifications.yaml").write_text('adresse: "https://grille-2027-notifications.exemple.workers.dev"\n',
                                                 encoding="utf-8")
    assert config.charger(tmp_path).notifications == "https://grille-2027-notifications.exemple.workers.dev/"
    (tmp_path / "notifications.yaml").write_text('adresse: "http://pas-chiffre.fr"\n', encoding="utf-8")
    conf = config.charger(tmp_path)
    assert conf.notifications == "" and "adresse invalide" in conf.anomalies[0]
