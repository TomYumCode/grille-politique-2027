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
        # Parti « Génération.s » : la ponctuation ignorée en faisait « génération s'approprie » (TF1, 31 octobre 2026).
        ("Les Docs du week-end", "Sur les réseaux sociaux ou en soirée, une nouvelle génération s'approprie désormais "
         "la culture western.", None),
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


@pytest.mark.parametrize("titre", ["Vous Présidente", "Vous Président : Bruno Retailleau", "Vous Président"])
def test_vous_president_toujours_dans_la_grille_et_la_campagne(politique, titre):
    """BFMTV, un candidat par soirée : retenue même sans description, interview, et dans le
    bouton « Présidentielle 2027 » (12 novembre 2026)."""
    from grille.campagne import Campagne
    from grille import invites_web
    f, chaines = politique
    d = f.decider(chaines["BFMTV"], titre, "")
    assert (d.filtre, d.categorie) == ("liste blanche", "interview")
    e = {"titre": titre, "invites": d.invites, "cites": d.cites, "categorie": d.categorie, "chaine": "BFMTV",
         "plateforme": "tv", "filtre": d.filtre, "nature": ""}
    assert Campagne(config.charger()).motif(e)
    assert invites_web.emission_a_invite(e, config.charger())  # invité cherché par Claude si inconnu


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
        # Précision entre virgules avant « sera interrogée » (« Vous Présidente », BFMTV, 12 novembre 2026).
        ("BFMTV", "Vous Présidente",
         "Marine Tondelier, candidate Les Ecologistes à l'élection présidentielle, sera interrogée sur les grandes "
         "orientations de son programme, sa conception du pouvoir, les ressorts de son engagement.", "",
         ["Marine Tondelier"], []),
        # Une précision suivie d'autre chose qu'un signe : seulement citée.
        ("France 5", "C pas si loin",
         "Marine Tondelier, candidate Les Ecologistes, a visité la Guadeloupe la semaine dernière.", "",
         [], ["Marine Tondelier"]),
        # Émission d'interview sans nom dans le titre : la première personne du résumé.
        ("Radio Classique", "L’invité de la matinale", "Marine Tondelier, candidate des Écologistes", "",
         ["Marine Tondelier"], []),
        # Sa propre chaîne.
        ("Jean-Luc Mélenchon", "Le peuple au pouvoir", "", "", ["Jean-Luc Mélenchon"], []),
        # Débat titré par une question sur lui, « avec » dans un autre membre de phrase : sujet, pas invité.
        ("France Culture", "Questions du soir : le débat",
         "Vainqueur de la primaire avec près de 66 % des voix, Raphaël Glucksmann revendique une ligne "
         "social-démocrate. Débat avec nos invités.",
         "Glucksmann candidat de la gauche : la social-démocratie fait-elle rêver ?", [], ["Raphaël Glucksmann"]),
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


@pytest.mark.parametrize("resume, retenue", [
    # Invités hors politique des 10 et 11 novembre 2026 : écartés.
    ("Ginette Kolinka est face à Marc-Olivier Fogiel", False),
    ("Maxime Gleizes, frère de Christophe Gleizes, est face à Marc-Olivier Fogiel", False),
    ("", False),
    # Personnalité de la liste, ou fonction politique : retenus.
    ("Gabriel Attal est face à Marc-Olivier Fogiel", True),
    ("Paul Dupont, député de la Somme, est face à Marc-Olivier Fogiel", True),
])
def test_face_a_fogiel_seulement_avec_invite_politique(politique, resume, retenue):
    f, chaines = politique
    assert (f.decider(chaines["RTL"], "Face à Fogiel", resume) is not None) is retenue
    assert f.motif_douteux("Face à Fogiel", resume) is not None


@pytest.mark.parametrize("chaine, titre", [
    ("BFMTV", "BFM Politique"), ("BFMTV", "Le grand oral 2027"), ("CNews", "100% Politique Week-End"),
    ("franceinfo", "L'invité politique"), ("France 5", "C politique, la suite"), ("LCP / Public Sénat", "Parlement hebdo"),
])
def test_rendez_vous_politiques_sans_invite_nomme(politique, chaine, titre):
    """Vus seulement en cas douteux jusqu'au 21 octobre 2026 : le guide ne nomme pas l'invité."""
    f, chaines = politique
    assert f.decider(chaines[chaine], titre, "").filtre == "liste blanche"


@pytest.mark.parametrize(
    "titre, description, retenu",
    [
        # Sigles de deux lettres (alias « PS », « RN ») : dans le titre, en majuscules, seuls.
        ("Le RN en tête des sondages", "", True),
        ("Le PS choisit son candidat", "", True),
        ("Sondage : le RN à 35 %", "", True),
        ("Accident sur la RN 7 : bouchons", "", False),  # route nationale
        ("Les jeux PS Plus de novembre", "", False),
        ("Test de la PS5 Pro", "", False),
        ("Recette du gâteau", "PS : abonnez-vous à la chaîne", False),  # post-scriptum
        ("Les ps de la vie", "", False),
    ],
)
def test_sigles_courts(politique, titre, description, retenu):
    f, chaines = politique
    assert (f.decider(chaines["France 2"], titre, description) is not None) == retenu


def test_sigle_court_douteux(politique):
    f, _ = politique
    assert f.motif_douteux("Meeting de R! à Paris") == "« R! » dans le titre"
    assert f.motif_douteux("Le meilleur du R&B") is None


@pytest.mark.parametrize("texte, attendu", [
    # Matinale de France Inter du 13 novembre 2026 : l'heure qui suit le nom.
    ("Le 6/9 reçoit Bruno Bobkiewicz, secrétaire général du Syndicat national des personnels de direction de "
     "l'Éducation nationale, à 6h20, François Ruffin, président du parti Debout ! à 7h50 et à 8h20, Antoine "
     "Foucher, président du cabinet Quintet.", [("François Ruffin", 7, 50)]),
    # L'heure juste avant le nom ; « 9 h 10 » avec espaces.
    ("À 8h20, Gabriel Attal répond aux questions. Puis Marine Tondelier à 9 h 10.",
     [("Gabriel Attal", 8, 20), ("Marine Tondelier", 9, 10)]),
    # Heure avant le nom (23 octobre 2026).
    ("Retrouvez vos rendez-vous. Et aujourd'hui à 6h20 Matthieu Lartot, journaliste sportif sur France "
     "Télévision à 7h50 Romain Boulet, co-président de l’ADAP, et à 8h20 Laure Lavalette, porte-parole du "
     "Rassemblement National, députée du Var.", [("Laure Lavalette", 8, 20)]),
    # La première personne du morceau : Jean-Luc Mélenchon n'est que cité (6 novembre 2026).
    ("Alexis Morel à la présentation du 6/9 reçoit Marie-Hélène Poingt, rédactrice en chef de La vie du rail "
     "à 6h20, Clémence Guetté, députée du Val-de-Marne, co-responsable du programme de Jean-Luc Mélenchon à "
     "7h50 et à 8h20, les auteurs du livre \"La nouvelle Armée des ombres\", enquête sur la DGSE.",
     [("Clémence Guetté", 7, 50)]),
    # Pas d'heure de passage (« le journal de 8 h »).
    ("François Ruffin publie un livre. Le journal de 8 h.", []),
])
def test_heures_annoncees(politique, texte, attendu):
    f, _ = politique
    assert f.heures_annoncees(texte) == attendu


def test_emission_reconnue_a_son_creneau(politique):
    """« À l'air libre » (Mediapart) : les directs du soir portent seulement le sujet du jour."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    paris = ZoneInfo("Europe/Paris")
    f, chaines = politique
    mediapart = chaines["Mediapart"]
    jeudi_19h = datetime(2026, 11, 12, 19, 2, tzinfo=paris)
    d = f.decider(mediapart, "Trump face à ses promesses : le bilan", "", debut=jeudi_19h)
    assert (d.filtre, d.emission) == ("liste blanche", "À l'air libre")
    # Nom déjà dans le titre : rien à ajouter en tête.
    assert f.decider(mediapart, "À l'air libre : spéciale présidentielle", "", debut=jeudi_19h).emission == ""
    # Hors créneau (vendredi, ou 21 h), ou autre chaîne : règle ordinaire.
    assert f.decider(mediapart, "Trump face à ses promesses : le bilan", "",
                     debut=datetime(2026, 11, 13, 19, 2, tzinfo=paris)) is None
    assert f.decider(mediapart, "Trump face à ses promesses : le bilan", "",
                     debut=datetime(2026, 11, 12, 21, 0, tzinfo=paris)) is None
    assert f.decider(chaines["Tocsin"], "Trump face à ses promesses", "", debut=jeudi_19h).emission == ""


def test_creneau_mal_ecrit_refuse(tmp_path):
    import shutil
    from pathlib import Path
    for nom in ("chaines.yaml", "politique.yaml"):
        shutil.copy(Path(config.DOSSIER_CONFIG) / nom, tmp_path / nom)
    p = tmp_path / "politique.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace("jours: [lundi, mardi, mercredi, jeudi]", "jours: [lundy]"),
                 encoding="utf-8")
    with pytest.raises(config.ErreurConfig, match="créneau"):
        config.charger(tmp_path)
