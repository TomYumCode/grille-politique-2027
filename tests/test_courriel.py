"""Email du matin : contenu, heure d'envoi, envoi unique."""

from datetime import datetime, timedelta

import pytest

from grille import config, courriel, db
from grille.tv import PARIS

MAINTENANT = datetime(2027, 3, 15, 7, 0, tzinfo=PARIS)


def _e(id_, debut, categorie="analyse", invites=(), **autres):
    return {"id": id_, "titre": f"Titre {id_}", "debut": debut.isoformat(), "fin": (debut + timedelta(hours=1)).isoformat(),
            "plateforme": "tv", "chaine": "France 2", "categorie": categorie, "invites": list(invites),
            "lien": ["https://www.france.tv/france-2/direct.html"], "statut": "annoncé", "filtre": "mots-clés", **autres}


@pytest.fixture
def connexion(tmp_path):
    c = db.ouvrir(tmp_path / "g.sqlite")
    yield c
    c.close()


def test_contenu_du_jour_et_temps_forts(connexion):
    emissions = [
        _e("hier-soir", MAINTENANT - timedelta(hours=10)),
        _e("ce-soir", MAINTENANT + timedelta(hours=14)),
        _e("demain-analyse", MAINTENANT + timedelta(days=1)),  # ni débat ni candidat : pas un temps fort
        _e("demain-debat", MAINTENANT + timedelta(days=1, hours=2), "débat"),
        _e("j3-candidat", MAINTENANT + timedelta(days=3), "interview", ["Marine Le Pen"]),
        _e("j4-meeting", MAINTENANT + timedelta(days=4), "meeting"),  # au-delà de 3 jours
    ]
    db.enregistrer_collecte(connexion, emissions, "tv", set(), MAINTENANT)
    c = courriel.contenu(connexion, config.charger(), MAINTENANT)
    assert c["titre_jour"] == "lundi 15 mars"
    assert [e["id"] for e in c["aujourdhui"]] == ["ce-soir"]
    assert [e["id"] for e in c["temps_forts"]] == ["demain-debat", "j3-candidat"]
    m = courriel.message(c)
    assert m["Subject"] == "Grille politique — lundi 15 mars : 1 émission"
    assert "https://www.france.tv/france-2/direct.html" in m.get_body(("plain",)).get_content()
    assert "Titre ce-soir" in m.get_body(("html",)).get_content()


def test_etat_des_sources(connexion):
    db.noter_collecte(connexion, "tv", MAINTENANT - timedelta(hours=1), True, 3, ["chaîne absente du guide : M6"])
    db.noter_collecte(connexion, "youtube", MAINTENANT - timedelta(hours=30), True, 2, [])
    db.noter_collecte(connexion, "youtube", MAINTENANT - timedelta(hours=1), False, 0, [], "quota épuisé")
    db.noter_collecte(connexion, "radio", MAINTENANT - timedelta(hours=1), True, 1, [])
    db.noter_collecte(connexion, "annonces", MAINTENANT - timedelta(hours=1), True, 1, [])
    alertes = db.etat_des_sources(connexion, MAINTENANT, courriel.SOURCES)
    assert alertes == [
        "Télévision : chaîne absente du guide : M6",
        "YouTube : aucune collecte réussie depuis 24 h (quota épuisé)",
        "Twitch : aucune collecte réussie depuis 24 h (aucune collecte enregistrée)",
    ]


@pytest.mark.parametrize(
    "heure_utc, attendu",
    [
        (datetime(2027, 6, 15, 4, 30), 1800),   # été : 6 h 30 à Paris → attendre 30 min
        (datetime(2027, 6, 15, 5, 30), 0),      # été, second déclenchement : 7 h 30 → tout de suite (doublon évité ailleurs)
        (datetime(2027, 1, 15, 4, 30), None),   # hiver : 5 h 30 à Paris → trop tôt, c'est l'autre déclenchement
        (datetime(2027, 1, 15, 5, 30), 1800),   # hiver : 6 h 30 → attendre 30 min
        (datetime(2027, 1, 15, 9, 30), None),   # 10 h 30 à Paris : trop tard
    ],
)
def test_attente_avant_7h(heure_utc, attendu):
    from datetime import timezone
    assert courriel.attente_avant_7h(heure_utc.replace(tzinfo=timezone.utc)) == attendu


def test_envoi_smtp(monkeypatch, connexion):
    envoyes = []

    class FauxSMTP:
        def __init__(self, serveur, port, timeout):
            assert (serveur, port) == ("smtp.mail.me.com", 587)
        def starttls(self, context):
            pass
        def login(self, utilisateur, mot_de_passe):
            assert (utilisateur, mot_de_passe) == ("moi@example.org", "mdp-application")
        def send_message(self, m):
            envoyes.append(m)
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(courriel.smtplib, "SMTP", FauxSMTP)
    for cle, valeur in {"SMTP_SERVEUR": "smtp.mail.me.com", "SMTP_UTILISATEUR": "moi@example.org",
                        "SMTP_MOT_DE_PASSE": "mdp-application", "EMAIL_DESTINATAIRE": "alias@example.org"}.items():
        monkeypatch.setenv(cle, valeur)
    monkeypatch.delenv("EMAIL_EXPEDITEUR", raising=False)
    courriel.envoyer(courriel.message(courriel.contenu(connexion, config.charger(), MAINTENANT)))
    assert envoyes[0]["To"] == "alias@example.org" and envoyes[0]["From"] == "moi@example.org"


def test_secrets_absents(monkeypatch, connexion):
    monkeypatch.delenv("SMTP_SERVEUR", raising=False)
    with pytest.raises(courriel.ConfigurationEmailIncomplete):
        courriel.envoyer(courriel.message(courriel.contenu(connexion, config.charger(), MAINTENANT)))


def test_un_seul_envoi_par_jour(connexion):
    assert not db.deja_envoye(connexion, "2027-03-15")
    db.noter_envoi(connexion, "2027-03-15", MAINTENANT)
    assert db.deja_envoye(connexion, "2027-03-15")
