"""Collecteur radio, à partir de réponses enregistrées de l'API Radio France."""

import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
import requests

from grille import acces, config, db, radio
from grille.acces import RADIOFRANCE_API
from grille.tv import PARIS
from tests.session_factice import Reponse, Session, charger

# À 6 h, la collecte lit aujourd'hui, demain et, à tour de rôle, le surlendemain (29 mars).
MAINTENANT = datetime(2027, 3, 27, 6, 0, tzinfo=PARIS)
API = charger("radiofrance_api.json")
CLE = "cle-secrete-123"
CHAINES = """\
chaines:
- {plateforme: radio, nom: "France Inter", adresse: "FRANCEINTER", categorie: "Radio publique", direct: "https://www.radiofrance.fr/franceinter"}
- {plateforme: radio, nom: "France Culture", adresse: "FRANCECULTURE", categorie: "Radio publique"}
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


def routeur(show_refuse=False, culture_en_panne=False):
    def repondre(methode, url, corps):
        assert (methode, url) == ("POST", RADIOFRANCE_API)
        requete = corps["query"]
        if "brands" in requete:
            return Reponse(corps=API["brands"])
        if show_refuse and "show" in requete:
            return Reponse(corps=API["erreur_show"])
        if "FRANCECULTURE" in requete:
            if culture_en_panne:
                raise requests.ConnectionError(f"Max retries exceeded with url: /v1/graphql?x-token={CLE}")
            grille = API["grid_FRANCECULTURE"]
        else:
            grille = API["grid_FRANCEINTER"]
        if not show_refuse:
            return Reponse(corps=grille)
        # Sans le champ « show », l'API renvoie les mêmes étapes sans nom d'émission.
        etapes = [{**e, "diffusion": {k: v for k, v in e["diffusion"].items() if k != "show"}} if "diffusion" in e
                  else e for e in grille["data"]["grid"]]
        return Reponse(corps={"data": {"grid": etapes}})
    return repondre


def test_une_requete_par_jour_et_au_plus_24_heures(conf, connexion):
    session = Session(routeur())
    radio.collecter(conf, session, connexion, MAINTENANT, cle=CLE)
    bornes = [tuple(int(x) for x in re.findall(r"(?:start|end): (\d+)", c[2]["query"])) for c in session.appels]
    assert len(bornes) == 2 * 3  # 2 stations × (aujourd'hui, demain, un jour suivant)
    assert all(fin - debut < 24 * 3600 for debut, fin in bornes)
    jours = sorted({datetime.fromtimestamp(debut, PARIS).date() for debut, _ in bornes})
    assert [j.day for j in jours] == [27, 28, 29]


def test_jour_de_25_heures():
    """Passage à l'heure d'hiver : deux requêtes pour couvrir le jour entier."""
    creneaux = radio.fenetres(date(2026, 10, 25))
    assert len(creneaux) == 2 and creneaux[0][0].hour == 0 and creneaux[-1][1].day == 26
    assert all(fin - debut < timedelta(hours=24) for debut, fin in creneaux)
    assert len(radio.fenetres(date(2026, 10, 26))) == 1


def _par_titre(rapport):
    return {e["titre"]: e for e in rapport.retenues}


def test_grille_filtree(conf, connexion):
    session = Session(routeur())
    rapport = radio.collecter(conf, session, connexion, MAINTENANT, cle=CLE)
    assert rapport.interrompu == "" and rapport.anomalies == []
    assert rapport.stations_lues == 2
    assert rapport.masques == 1  # rediffusion de 3 h
    retenues = _par_titre(rapport)
    assert set(retenues) == {
        "Questions politiques — Édouard Philippe",
        "L'invité de 8h20 : le grand entretien — Marine Tondelier, invitée de 8h20",
        "Le magazine de la rédaction — La présidentielle vue des régions",
    }
    qp = retenues["Questions politiques — Édouard Philippe"]
    assert qp["filtre"] == "liste blanche" and qp["categorie"] == "interview"
    assert qp["invites"] == ["Édouard Philippe"]
    assert qp["debut"] == "2027-03-27T12:00:00+01:00" and qp["fin"] == "2027-03-27T13:00:00+01:00"
    assert qp["id"] == "radio:FRANCEINTER:202703271200"
    assert qp["lien"] == ["https://www.radiofrance.fr/franceinter",
                          "https://www.radiofrance.fr/franceinter/podcasts/questions-politiques/"
                          "questions-politiques-du-samedi-27-mars-2027"]
    tondelier = retenues["L'invité de 8h20 : le grand entretien — Marine Tondelier, invitée de 8h20"]
    assert tondelier["filtre"] == "mots-clés" and tondelier["invites"] == ["Marine Tondelier"]
    assert tondelier["debut"] == "2027-03-29T08:20:00+02:00"  # passage à l'heure d'été
    # La clé passe en paramètre, jamais dans le corps de la requête.
    assert all(CLE not in str(corps) for _, _, corps in session.appels)
    en_base = db.lister(connexion, MAINTENANT, datetime(2027, 4, 4, tzinfo=PARIS))
    assert {e["plateforme"] for e in en_base} == {"radio"} and len(en_base) == 3


def test_nom_d_emission_refuse(conf, connexion):
    session = Session(routeur(show_refuse=True))
    rapport = radio.collecter(conf, session, connexion, MAINTENANT, cle=CLE)
    assert rapport.stations_lues == 2 and not rapport.interrompu
    assert rapport.anomalies == ["Radio France : nom des émissions (« show ») refusé, titres seuls"]
    # Sans le nom d'émission, « Édouard Philippe » est retenu par les mots-clés.
    assert {e["titre"] for e in rapport.retenues} == {
        "Édouard Philippe", "Marine Tondelier, invitée de 8h20", "La présidentielle vue des régions"}
    assert len(session.appels) == 1 + 2 * 3  # un essai refusé, puis une requête par station et par jour


def test_station_en_panne_cle_masquee(conf, connexion):
    radio.collecter(conf, Session(routeur()), connexion, MAINTENANT, cle=CLE)
    rapport = radio.collecter(conf, Session(routeur(culture_en_panne=True)), connexion, MAINTENANT, cle=CLE)
    assert rapport.stations_lues == 1 and not rapport.interrompu
    assert len(rapport.anomalies) == 1 and "France Culture" in rapport.anomalies[0]
    assert CLE not in rapport.anomalies[0] and "x-token=***" in rapport.anomalies[0]
    # La station en panne n'est pas couverte : ses émissions ne passent pas en « annulé ».
    assert rapport.annulees == 0
    titres = {e["titre"] for e in db.lister(connexion, MAINTENANT, datetime(2027, 4, 4, tzinfo=PARIS))}
    assert "Le magazine de la rédaction — La présidentielle vue des régions" in titres


def test_sans_cle(conf, connexion, monkeypatch):
    monkeypatch.delenv("RADIOFRANCE_API_KEY", raising=False)
    rapport = radio.collecter(conf, Session(routeur()), connexion, MAINTENANT)
    assert rapport.interrompu == "secret RADIOFRANCE_API_KEY absent"


def test_station_inconnue(conf, connexion):
    def repondre(methode, url, corps):
        return Reponse(corps=API["erreur_station"])
    rapport = radio.collecter(conf, Session(repondre), connexion, MAINTENANT, cle=CLE)
    assert rapport.stations_lues == 0
    assert "StationsEnum" in rapport.interrompu


def test_verifier_acces(conf, monkeypatch):
    monkeypatch.setenv("RADIOFRANCE_API_KEY", CLE)
    r = acces.verifier_radiofrance(conf, Session(routeur()))
    assert (r.etat, r.detail) == ("ok", "clé acceptée ; 2/2 stations reconnues")


def test_ancienne_base_migree(tmp_path):
    """Une base de version 4 (sans « radio » dans la contrainte) est recopiée sans perte."""
    import sqlite3

    chemin = tmp_path / "ancienne.sqlite"
    ancienne = sqlite3.connect(chemin)
    ancienne.executescript(db.SCHEMA.replace("'tv', 'radio', 'youtube'", "'tv', 'youtube'"))
    ancienne.execute("INSERT INTO emissions (id, titre, debut, plateforme, chaine, vu_le) VALUES "
                     "('tv:1', 'Franc-jeu', '2027-03-15T13:20:00+01:00', 'tv', 'France 2', '2027-03-15T10:00:00+01:00')")
    ancienne.commit()
    ancienne.close()
    connexion = db.ouvrir(chemin)
    assert connexion.execute("SELECT titre FROM emissions").fetchall() == [("Franc-jeu",)]
    connexion.execute("INSERT INTO emissions (id, titre, debut, plateforme, chaine, vu_le) VALUES "
                      "('radio:1', 'x', '2027-03-15T13:20:00+01:00', 'radio', 'France Inter', '2027-03-15T10:00:00+01:00')")
    assert connexion.execute("SELECT 1 FROM sqlite_master WHERE name = 'emissions_debut'").fetchone() == (1,)
    connexion.close()
    db.ouvrir(chemin).close()  # deuxième ouverture : rien à migrer


def test_creneau_vide_nomme_d_apres_la_semaine_precedente(tmp_path, connexion):
    """Radio France ne relie la diffusion à son créneau qu'au dernier moment : d'ici là, le
    créneau vide prend le nom de l'émission diffusée à la même heure sept jours plus tôt."""
    (tmp_path / "chaines.yaml").write_text(
        'chaines:\n- {plateforme: radio, nom: "France Culture", adresse: "FRANCECULTURE", categorie: "Radio publique"}\n',
        encoding="utf-8")
    shutil.copy(Path(config.DOSSIER_CONFIG) / "politique.yaml", tmp_path / "politique.yaml")
    conf = config.charger(tmp_path)
    vides = charger("radiofrance_creneaux_vides.json")
    lus = []

    def repondre(methode, url, corps):
        debut = datetime.fromtimestamp(int(re.search(r"start: (\d+)", corps["query"]).group(1)), PARIS)
        lus.append(debut.date())
        grilles = {date(2026, 10, 12): "lundi_12_octobre", date(2026, 10, 19): "lundi_19_octobre"}
        return Reponse(corps=vides[grilles[debut.date()]] if debut.date() in grilles else {"data": {"grid": []}})

    rapport = radio.collecter(conf, Session(repondre), connexion, datetime(2026, 10, 19, 10, 0, tzinfo=PARIS), cle=CLE)
    assert [(e["id"], e["titre"], e["categorie"]) for e in rapport.retenues] == [
        ("radio:FRANCECULTURE:202610191820", "Questions du soir : le débat", "débat")]
    # La semaine précédente n'est lue que pour le jour qui a des créneaux vides (le 25, jour de
    # 25 heures, demande deux requêtes).
    assert lus == [date(2026, 10, d) for d in (19, 12, 20, 25, 25)]
