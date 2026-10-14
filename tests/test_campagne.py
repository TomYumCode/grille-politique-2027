"""Bouton « Présidentielle 2027 » : émissions consacrées à la campagne."""

import pytest

from grille import campagne, config


@pytest.fixture(scope="module")
def classer():
    return campagne.Campagne(config.charger()).motif


def _e(titre, chaine="France 2", categorie="analyse", invites=(), cites=(), resume=""):
    return {"titre": titre, "chaine": chaine, "plateforme": "tv", "categorie": categorie,
            "invites": list(invites), "cites": list(cites), "resume": resume}


@pytest.mark.parametrize("emission, dedans", [
    # Candidat ou membre d'équipe de campagne présent.
    (_e("Franc-jeu", invites=["Gabriel Attal"]), True),
    (_e("Jean-Philippe Tanguy sur RTL", chaine="RTL", categorie="interview", invites=["Jean-Philippe Tanguy"]), True),
    # Personnalité sans rôle de campagne : pas d'office.
    (_e("L'invité de 8h20", invites=["Mathilde Panot"]), False),
    # Candidat nommé dans le titre d'un commentaire ; cité seulement dans le résumé : non.
    (_e("Glucksmann : gros scandale électoral ?", chaine="Juste Milieu", cites=["Raphaël Glucksmann"]), True),
    (_e("Trump, Poutine et Zelensky", chaine="Ligne Droite", cites=["Jean-Luc Mélenchon"],
        resume="Avec un mot sur Mélenchon"), False),
    # Meeting, chaîne de parti, mot de campagne dans le titre ou le résumé.
    (_e("Réunion publique à Frontignan", chaine="La France insoumise", categorie="meeting"), True),
    (_e("Vlog du dimanche", chaine="Rassemblement National"), True),
    (_e("Controverse — Faut-il interdire les sondages ?", chaine="LCP / Public Sénat"), True),
    (_e("C politique", chaine="France 5", resume="Les candidats à la présidentielle face aux jeunes."), True),
    # Actualité politique hors campagne.
    (_e("Questions au gouvernement", chaine="LCP / Public Sénat"), False),
    (_e("Budget 2027 : débat sur la dette", chaine="LCP - Assemblée nationale", categorie="débat"), False),
])
def test_classement(classer, emission, dedans):
    assert bool(classer(emission)) is dedans


def test_tocsin_toujours_retenu_mais_pas_forcement_campagne(classer):
    """Liste blanche : toute matinale de Tocsin entre dans « Toute la politique » ; elle n'entre
    dans « Présidentielle 2027 » que si son contenu propre parle de la campagne."""
    from grille.filtre import FiltrePolitique
    conf = config.charger()
    tocsin = next(c for c in conf.chaines if c.nom == "Tocsin")
    decision = FiltrePolitique(conf).decider(tocsin, "La Matinale du 14/10 : la France sous la tutelle de la BCE ?", "")
    assert decision is not None and decision.filtre == "liste blanche"
    assert not classer(_e("La Matinale du 14/10 : la France sous la tutelle de la BCE ?", chaine="Tocsin"))
