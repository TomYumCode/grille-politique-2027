"""Phrase de la radio qui présente un invité inconnu de l'outil (page et email)."""

from datetime import date

from grille import affichage, radios_privees
from tests.session_factice import REPONSES

RADIOCLASSIQUE = (REPONSES / "radio_radioclassique.html").read_text(encoding="utf-8")


def _emission(titre, resume, plateforme="radio", invites=()):
    return {"titre": titre, "resume": resume, "plateforme": plateforme, "invites": list(invites)}


def test_invite_presente_par_la_radio():
    p = {x.titre: x for x in radios_privees.lire_radioclassique(
        RADIOCLASSIQUE, "https://www.radioclassique.fr/grille-des-programmes/2026-10-13/", date(2026, 10, 13))}
    invite = p["L’invité de la matinale"]
    assert affichage.presentation(_emission(invite.titre, invite.description)).startswith("Anne Goscinny, co-auteure")


def test_premiere_phrase_et_longueur_limitee():
    resume = "Patrick Martin, président du Medef, est l'invité des Matins. Il revient sur la dette. " * 3
    assert affichage.presentation(_emission("L'Invité(e) des Matins", resume)) == \
        "Patrick Martin, président du Medef, est l'invité des Matins."
    long = "Dominique Schelcher " + "très " * 60 + "long."
    texte = affichage.presentation(_emission("L'invité RTL de 7h40", long))
    assert texte.endswith("…") and len(texte) <= affichage.LONGUEUR_PRESENTATION


def test_pas_de_presentation():
    # Invité déjà connu, télévision (résumé qui décrit l'émission), émission sans invité.
    assert affichage.presentation(_emission("L'invité RTL de 7h40", "Gabriel Attal répond.", invites=["Gabriel Attal"])) == ""
    assert affichage.presentation(_emission("C à vous l'invité", "Installés dans le loft…", plateforme="tv")) == ""
    assert affichage.presentation(_emission("Le journal de 8h", "Les titres de l'actualité.")) == ""
