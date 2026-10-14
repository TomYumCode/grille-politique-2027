import pytest

from grille import config, filtre


@pytest.fixture(scope="module")
def politique():
    conf = config.charger()
    chaines = {c.nom: c for c in conf.chaines}
    return filtre.FiltrePolitique(conf), chaines


def test_normaliser():
    assert filtre.normaliser("  L'Élysée : DÉBAT d'entre-deux-tours ! ") == "l elysee debat d entre deux tours"


@pytest.mark.parametrize(
    "titre, description, attendu",
    [
        ("Les quatre vérités", "", ("liste blanche", "interview")),
        ("Soirée électorale", "Résultats du second tour", ("mots-clés", "analyse")),
        ("Le grand entretien", "Avec Marine Tondelier", ("mots-clés", "interview")),
        ("Météo", "", None),
        ("28 minutes", "Le magazine de débat d'Arte sur l'actualité.", None),  # « débat » hors du titre
        ("28 minutes", "Débat avec Raphaël Glucksmann.", ("mots-clés", "débat")),  # mais un candidat suffit
        ("Le débat de la semaine", "", ("mots-clés", "débat")),
        ("Franc-jeu", "", ("liste blanche", "analyse")),  # titre commençant par une émission de la liste
        ("Franc jeu — Gabriel Attal face à Marion Maréchal", "", ("liste blanche", "analyse")),
        ("Franchise", "", None),
        # « Face à face » n'est en liste blanche que sur BFMTV, mais un ministre invité suffit ailleurs.
        ("Face à face", "Avec un ministre", ("mots-clés", "débat")),
        ("Face à face", "Avec un chef étoilé", None),
        ("Réunion publique à Saint-Ouen | Présidentielle 2027", "", ("mots-clés", "meeting")),
        ("L'heure de vérité", "Avec Édouard Philippe", ("mots-clés", "interview")),
        ("Élection de Miss France 2027", "", None),
        ("Les Horizons perdus", "Film d'aventure", None),  # parti ambigu
        ("Attalens, village suisse", "", None),  # « Attal » seulement en mot entier
    ],
)
def test_decider(politique, titre, description, attendu):
    f, chaines = politique
    decision = f.decider(chaines["France 2"], titre, description)
    assert (decision and (decision.filtre, decision.categorie)) == attendu or (attendu is None and decision is None)


def test_chaine_de_parti_toujours_retenue(politique):
    f, chaines = politique
    decision = f.decider(chaines["Rassemblement National"], "Vlog du dimanche", "")
    assert decision.filtre == "liste blanche"


def test_emission_limitee_a_une_chaine(politique):
    f, chaines = politique
    assert f.decider(chaines["BFMTV"], "Face-à-Face", "").filtre == "liste blanche"
    assert f.decider(chaines["France 5"], "Face à face avec les requins", "") is None


@pytest.mark.parametrize(
    "chaine, titre, description, sous_titre, presents, cites",
    [
        # Commentaires d'actualité sur Twitch : les noms sont des sujets.
        ("Clemovitch (Clément Viktorovitch)",
         "Glucksmann : la surprise ? Mélenchon : sa proposition choc pour la jeunesse | Le Café Rhétorique", "", "",
         [], ["Jean-Luc Mélenchon", "Raphaël Glucksmann"]),
        ("BackSeat (Jean Massiet)", "GLUCKSMANN ÉLU PRÉSIDENT DE LA RÉPUBLIQUE (ah non pas encore) - !Backseat", "", "",
         [], ["Raphaël Glucksmann"]),
        ("Hugo au Perchoir", "Réaction au meeting de Mélenchon", "", "", [], ["Jean-Luc Mélenchon"]),
        # Interviews, invités, meetings : présents.
        ("CNews", "L'interview", "", "Jean-Luc Mélenchon", ["Jean-Luc Mélenchon"], []),
        ("Hugo au Perchoir", "Interview de Jordan Bardella", "", "", ["Jordan Bardella"], []),
        ("La France insoumise", "Meeting de Jean-Luc Mélenchon à Clermont-Ferrand", "", "", ["Jean-Luc Mélenchon"], []),
        ("France 2", "Franc-jeu", "", "Gabriel Attal", ["Gabriel Attal"], []),
        ("France 2", "Les quatre vérités", "Invitée : Laure Lavalette. Elle répond aux attaques de Gabriel Attal.", "",
         ["Laure Lavalette"], ["Gabriel Attal"]),
        ("France 5", "C à vous", "Avec Gabriel Attal et Marine Tondelier, puis Bruno Retailleau en duplex.", "",
         ["Gabriel Attal", "Bruno Retailleau", "Marine Tondelier"], []),
        ("BFMTV", "Face à face", "Apolline de Malherbe reçoit Jordan Bardella.", "", ["Jordan Bardella"], []),
        # Émission d'interview sans nom dans le titre : la première personne du résumé.
        ("Radio Classique", "L’invité de la matinale", "Marine Tondelier, candidate des Écologistes", "",
         ["Marine Tondelier"], []),
        # Sa propre chaîne.
        ("Jean-Luc Mélenchon", "Le peuple au pouvoir", "", "", ["Jean-Luc Mélenchon"], []),
    ],
)
def test_presents_ou_cites(politique, chaine, titre, description, sous_titre, presents, cites):
    f, chaines = politique
    decision = f.decider(chaines[chaine], titre, description, sous_titre=sous_titre)
    assert (sorted(decision.invites), sorted(decision.cites)) == (sorted(presents), sorted(cites))


def test_rediffusion_d_un_meeting(politique):
    """CNews titre « L'interview — Jean-Luc Mélenchon » la rediffusion de son meeting."""
    f, chaines = politique
    decision = f.decider(chaines["CNews"], "L'interview", "Rediffusion du meeting de Jean-Luc Mélenchon à Clermont-Ferrand.",
                         sous_titre="Jean-Luc Mélenchon")
    assert decision.categorie == "meeting"
    assert f.decider(chaines["CNews"], "L'interview", "Au lendemain de son meeting, il répond à nos questions.",
                     sous_titre="Jean-Luc Mélenchon").categorie == "interview"
    assert f.decider(chaines["Hugo au Perchoir"], "Réaction au meeting de Mélenchon", "").categorie == "analyse"


@pytest.mark.parametrize("emission, sous_titre, retenue", [
    # Radio France publie l'invité la veille : une fonction politique suffit (13 et 14 octobre 2026).
    ("L'Invité de 7h50", "Edouard Geffray, ministre de l'Education nationale", True),
    ("L'Invité de 8h20 : le grand entretien", "Gérard Davet et Fabrice Lhomme", False),
    # Natacha Polony, journaliste… puis candidate déclarée ce même 14 octobre : retenue.
    ("L'Invité de 7h50", "Natacha Polony", True),
    ("L'Invité de 7h50", "Fabrice Luchini", False),
    ("L'invité du 13/14", "Zita et le professeur Guillaume Bronsard", False),
    # Hors émission à invités, la fonction seule ne suffit pas (journal, documentaire…).
    ("Le journal de 8h", "Le ministre de l'Intérieur annonce un plan", False),
])
def test_invite_avec_fonction_politique(politique, emission, sous_titre, retenue):
    f, chaines = politique
    assert (f.decider(chaines["France Inter"], emission, "", sous_titre=sous_titre) is not None) is retenue
