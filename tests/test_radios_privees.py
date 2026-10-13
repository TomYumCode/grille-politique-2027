"""Radios privées, à partir d'extraits réels des grilles de RTL, Europe 1, Sud Radio, RMC et Radio Classique."""

from datetime import date, datetime

import pytest
import requests

from grille import affichage, config, db, radios_privees
from grille.tv import PARIS
from tests.session_factice import REPONSES

RTL = (REPONSES / "radio_rtl.html").read_text(encoding="utf-8")
EUROPE1 = (REPONSES / "radio_europe1.html").read_text(encoding="utf-8")
SUDRADIO = (REPONSES / "radio_sudradio.html").read_text(encoding="utf-8")
RMC = (REPONSES / "radio_rmc.html").read_text(encoding="utf-8")
RADIOCLASSIQUE = (REPONSES / "radio_radioclassique.html").read_text(encoding="utf-8")
MAINTENANT = datetime(2026, 10, 12, 6, 30, tzinfo=PARIS)  # lundi


class ReponseHtml:
    def __init__(self, texte):
        self.text, self.status_code, self.encoding = texte, 200, "utf-8"

    def raise_for_status(self):
        pass


class SessionHtml:
    def __init__(self, pages):
        self.pages, self.appels = pages, []

    def get(self, url, **kwargs):
        self.appels.append(url)
        for debut, page in self.pages.items():
            if url.startswith(debut):
                if isinstance(page, Exception):
                    raise page
                return ReponseHtml(page)
        return ReponseHtml("<html>vide</html>")


@pytest.fixture
def conf():
    return config.charger()


def test_rtl():
    p = {x.titre: x for x in radios_privees.lire_rtl(RTL, "https://www.rtl.fr/grille/13-10-2026", date(2026, 10, 13))}
    invite = p["L'invité RTL de 7h40"]
    assert (invite.debut.isoformat(), invite.fin.isoformat()) == ("2026-10-13T07:43:00+02:00", "2026-10-13T07:55:00+02:00")
    assert p["RTL Matin"].fin.isoformat() == "2026-10-13T09:00:00+02:00"
    assert p["Face à Fogiel"].debut.hour == 8
    # Après minuit, la grille continue sur le lendemain.
    assert p["Un jour, une vie"].debut.isoformat() == "2026-10-14T00:30:00+02:00"


def test_rtl_emission_en_cours_sans_horaire(conf, tmp_path):
    """Pendant RTL Matin, sa carte n'a pas d'horaire (« programme-card--direct ») : ses chroniques
    restent lues et ne passent pas en « annulé » (13 octobre 2026, 7 h 36)."""
    en_direct = RTL.replace('<div class="programme-card "', '<div class="programme-card programme-card--direct"', 1)
    en_direct = en_direct.replace(">07h00 - 09h00</h2>", "></h2>", 1)
    p = {x.titre: x for x in radios_privees.lire_rtl(en_direct, "https://www.rtl.fr/grille/13-10-2026", date(2026, 10, 13))}
    assert p["RTL Matin"].debut.isoformat() == "2026-10-13T07:00:00+02:00"
    assert p["L'invité RTL de 7h40"].debut.isoformat() == "2026-10-13T07:43:00+02:00"
    # Collecte de 7 h 36 après une collecte de la veille : rien n'est annulé.
    connexion = db.ouvrir(tmp_path / "g.sqlite")
    veille = datetime(2026, 10, 12, 20, 0, tzinfo=PARIS)
    radios_privees.collecter(conf, SessionHtml({"https://www.rtl.fr/grille": RTL}), connexion, veille)
    rapport = radios_privees.collecter(conf, SessionHtml({"https://www.rtl.fr/grille": en_direct}), connexion,
                                       datetime(2026, 10, 13, 7, 36, tzinfo=PARIS))
    assert rapport.annulees == 0
    assert any(e["titre"] == "L'invité RTL de 7h40" for e in rapport.retenues)
    connexion.close()


def test_europe1_grille_type_placee_sur_la_semaine():
    p = radios_privees.lire_europe1(EUROPE1, "https://www.europe1.fr/grille-des-programmes", date(2026, 10, 12))
    gi = [x for x in p if x.titre.startswith("La Grande interview")]
    assert [x.debut.isoformat() for x in gi][:2] == ["2026-10-12T08:10:00+02:00", "2026-10-13T08:10:00+02:00"]
    assert gi[0].lien == "https://www.europe1.fr/emissions/la-grande-interview-europe-1-cnews"
    # Mercredi dernier : placé sur le mercredi qui vient, pas dans le passé.
    assert min(x.debut for x in p).date() == date(2026, 10, 12)


def test_sudradio():
    p = radios_privees.lire_sudradio(SUDRADIO, "https://www.sudradio.fr/programmes", date(2026, 10, 12))
    titres = {x.titre: x for x in p}
    assert titres["L'invité politique Sud Radio"].debut.isoformat() == "2026-10-12T08:30:00+02:00"
    assert titres["Le journal de 7h"].description.startswith("Glucksmann remporte la primaire")


def test_rmc_grille_de_la_semaine():
    p = radios_privees.lire_rmc(RMC, "https://rmc.bfmtv.com/grille-radio/", date(2026, 10, 12))
    face = [x for x in p if x.titre == "Face à Face"]
    # Du lundi au vendredi ; une émission finit quand la suivante commence.
    assert [x.debut.isoformat() for x in face][:2] == ["2026-10-12T08:29:00+02:00", "2026-10-13T08:29:00+02:00"]
    assert face[0].fin.isoformat() == "2026-10-12T08:51:00+02:00"
    assert face[0].lien == "https://www.bfmtv.com/replay-emissions/l-interview/"
    # La carte de l'émission en cours (classe « current ») n'est pas oubliée.
    assert any(x.titre == "Super Moscato Show" and x.debut.isoformat() == "2026-10-12T15:00:00+02:00" for x in p)
    assert max(x.debut for x in p).date() == date(2026, 10, 18)
    with pytest.raises(radios_privees.PageIllisible):
        radios_privees.lire_rmc("<html>travaux</html>", "https://rmc.bfmtv.com/grille-radio/", date(2026, 10, 12))


def test_radioclassique():
    p = {x.titre: x for x in radios_privees.lire_radioclassique(
        RADIOCLASSIQUE, "https://www.radioclassique.fr/grille-des-programmes/2026-10-13/", date(2026, 10, 13))}
    invite = p["L’invité de la matinale"]
    assert (invite.debut.isoformat(), invite.fin.isoformat()) == ("2026-10-13T08:15:00+02:00", "2026-10-13T08:30:00+02:00")
    assert invite.description.startswith("Anne Goscinny")
    assert p["La matinale de Radio Classique"].fin.isoformat() == "2026-10-13T09:00:00+02:00"
    # Heure donnée en UTC dans la page : minuit à Paris.
    assert p["Les disques de légendes"].debut.isoformat() == "2026-10-13T00:00:00+02:00"
    assert p["Votre soirée Classique"].fin.isoformat() == "2026-10-14T00:00:00+02:00"


def test_semaine_suivante_vide_n_est_pas_une_panne():
    assert radios_privees.lire_sudradio('<ul class="sud_planning_jour"></ul>', "https://www.sudradio.fr/programmes?week=1",
                                        date(2026, 10, 12)) == []
    with pytest.raises(radios_privees.PageIllisible):
        radios_privees.lire_sudradio("<html>travaux</html>", "https://www.sudradio.fr/programmes", date(2026, 10, 12))


def test_collecte(conf, tmp_path):
    connexion = db.ouvrir(tmp_path / "g.sqlite")
    # L'invité de la matinale de Radio Classique, ce jour-là, est une candidate.
    radioclassique = RADIOCLASSIQUE.replace("Anne Goscinny, co-auteure", "Marine Tondelier, candidate des Écologistes")
    session = SessionHtml({"https://www.rtl.fr/grille": RTL, "https://www.europe1.fr": EUROPE1,
                           "https://www.sudradio.fr/programmes": SUDRADIO, "https://rmc.bfmtv.com": RMC,
                           "https://www.radioclassique.fr/grille-des-programmes/2026-10-13/": radioclassique})
    rapport = radios_privees.collecter(conf, session, connexion, MAINTENANT)
    assert rapport.radios_lues == 5 and not rapport.interrompu
    assert "https://www.radioclassique.fr/grille-des-programmes/2026-10-12/" in session.appels
    # RTL : aujourd'hui, demain et un jour suivant à tour de rôle ; Sud Radio : deux semaines.
    assert session.appels[:3] == ["https://www.rtl.fr/grille/12-10-2026", "https://www.rtl.fr/grille/13-10-2026",
                                  "https://www.rtl.fr/grille/14-10-2026"]
    assert "https://www.sudradio.fr/programmes?week=1" in session.appels
    titres = {(e["chaine"], e["titre"]) for e in rapport.retenues}
    assert ("RTL", "L'invité RTL de 7h40") in titres
    assert ("RTL", "Face à Fogiel") in titres
    assert ("Europe 1", "La Grande interview Europe 1 - CNews") in titres
    assert ("Sud Radio", "L'invité politique Sud Radio") in titres
    assert ("RMC", "Face à Face") in titres
    invite = next(e for e in rapport.retenues if e["chaine"] == "Radio Classique")
    assert (invite["titre"], invite["invites"]) == ("L’invité de la matinale", ["Marine Tondelier"])
    # Un journal qui cite un candidat dans son résumé n'est pas une émission politique.
    assert ("Sud Radio", "Le journal de 7h") not in titres
    assert all(e["plateforme"] == "radio" for e in rapport.retenues)
    connexion.close()


def test_agenda_rattache_a_l_invite_rtl(conf, tmp_path):
    """« Jean-Philippe Tanguy sera l'invité de RTL le mardi 13 octobre à 7h40 » rejoint « L'invité RTL de 7h40 »."""
    connexion = db.ouvrir(tmp_path / "g.sqlite")
    session = SessionHtml({"https://www.rtl.fr/grille": RTL})
    radios_privees.collecter(conf, session, connexion, MAINTENANT)
    rdv = {"id": "web:rn:1", "titre": "Jean-Philippe Tanguy sur RTL", "debut": "2026-10-13T07:40:00+02:00", "fin": None,
           "plateforme": "web", "chaine": "RTL", "categorie": "interview", "invites": ["Jean-Philippe Tanguy"],
           "lien": [], "statut": "annoncé", "filtre": "mots-clés"}
    db.enregistrer_collecte(connexion, [rdv], "web", set(), MAINTENANT)
    emissions = affichage.emissions(connexion, MAINTENANT, datetime(2026, 10, 14, tzinfo=PARIS))
    invite = next(e for e in emissions if e["titre"] == "L'invité RTL de 7h40" and e["debut"].startswith("2026-10-13"))
    assert invite["invites"] == ["Jean-Philippe Tanguy"]
    assert not any(e["titre"] == "Jean-Philippe Tanguy sur RTL" for e in emissions)
    connexion.close()


def test_page_changee(conf, tmp_path):
    connexion = db.ouvrir(tmp_path / "g.sqlite")
    rapport = radios_privees.collecter(conf, SessionHtml({"https://": requests.ConnectionError("coupure")}),
                                       connexion, MAINTENANT)
    assert rapport.interrompu.startswith("aucune grille de radio privée lisible")
    connexion.close()
