"""Dédoublonnage : une même diffusion sur plusieurs chaînes ne fait qu'une émission."""

from datetime import datetime

from grille import courriel, db, fusion, page
from grille.config import charger
from grille.tv import PARIS


def emission(id_, titre, debut, plateforme, chaine, lien, **autres):
    return {"id": id_, "titre": titre, "debut": debut, "fin": autres.get("fin"), "plateforme": plateforme,
            "chaine": chaine, "categorie": autres.get("categorie", "analyse"), "invites": autres.get("invites", []),
            "lien": lien, "statut": autres.get("statut", "annoncé"), "filtre": autres.get("filtre", "liste blanche")}


LCP = emission("tv:LCP:1", "Questions au gouvernement", "2027-03-30T15:02:00+02:00", "tv", "LCP / Public Sénat",
               ["https://www.france.tv/lcp-public-senat/direct.html"], fin="2027-03-30T16:10:00+02:00")
BACKSEAT = emission("twitch:1", "Questions au Gouvernement à l'Assemblée", "2027-03-30T15:00:00+02:00", "twitch",
                    "BackSeat (Jean Massiet)", ["https://www.twitch.tv/jeanmassiet"], statut="en direct")
DEBRIEF = emission("tv:LCP:2", "Questions au gouvernement - le débrief", "2027-03-30T16:17:00+02:00", "tv",
                   "LCP / Public Sénat", ["https://www.france.tv/lcp-public-senat/direct.html"])


def test_debat_sur_deux_plateformes_une_seule_fois():
    """Critère du lot 6 : une seule émission, avec ses deux liens."""
    resultat = fusion.fusionner([BACKSEAT, LCP, DEBRIEF])
    assert len(resultat) == 2
    qag = resultat[0]
    assert qag["chaine"] == "LCP / Public Sénat" and qag["plateforme"] == "tv"  # la télévision porte la carte
    assert qag["debut"] == LCP["debut"] and qag["titre"] == "Questions au gouvernement"
    assert qag["lien"] == ["https://www.france.tv/lcp-public-senat/direct.html", "https://www.twitch.tv/jeanmassiet"]
    assert [(s["chaine"], s["plateforme"]) for s in qag["sources"]] == [
        ("LCP / Public Sénat", "tv"), ("BackSeat (Jean Massiet)", "twitch")]
    assert qag["statut"] == "en direct"
    assert "sources" not in resultat[1]  # le débrief, seul, reste tel quel


def test_meme_chaine_jamais_fusionnee():
    a = emission("youtube:1", "Meeting de Lyon", "2027-03-30T15:00:00+02:00", "youtube", "Gabriel Attal", [])
    b = emission("youtube:2", "Meeting de Lyon", "2027-03-30T15:05:00+02:00", "youtube", "Gabriel Attal", [])
    assert len(fusion.fusionner([a, b])) == 2


def test_trop_eloignees_ou_titres_differents():
    tard = dict(BACKSEAT, debut="2027-03-30T14:00:00+02:00")  # une heure avant
    assert len(fusion.fusionner([tard, LCP])) == 2
    autre = emission("youtube:3", "Le grand débat des régions", "2027-03-30T15:00:00+02:00", "youtube", "Public Sénat", [])
    assert len(fusion.fusionner([autre, LCP])) == 2


def test_meme_emetteur_sur_deux_plateformes():
    """22 octobre 2026 : le même meeting en direct sur YouTube et sur Twitch, titré autrement."""
    yt = emission("youtube:r", "Réunion publique à Rochefort | Présidentielle 2027", "2026-10-22T19:31:00+02:00",
                  "youtube", "La France insoumise", ["https://www.youtube.com/watch?v=x"], categorie="meeting")
    tw = emission("twitch:r", "Réunion publique à Rochefort avec Mathilde Panot et Antoine Léaument",
                  "2026-10-22T19:30:00+02:00", "twitch", "La France insoumise", ["https://www.twitch.tv/lfi"],
                  categorie="meeting", invites=["Mathilde Panot"])
    [carte] = fusion.fusionner([yt, tw])
    assert carte["plateforme"] == "youtube" and carte["invites"] == ["Mathilde Panot"]
    assert carte["lien"] == ["https://www.youtube.com/watch?v=x", "https://www.twitch.tv/lfi"]
    # Autre émetteur, ou un seul mot en commun, ou trop d'écart : deux cartes.
    assert len(fusion.fusionner([yt, dict(tw, chaine="Clemovitch (Clément Viktorovitch)")])) == 2
    assert len(fusion.fusionner([yt, dict(tw, titre="Rochefort ce soir")])) == 2
    assert len(fusion.fusionner([yt, dict(tw, debut="2026-10-22T19:45:00+02:00")])) == 2
    # Le nom de l'émetteur dans les deux titres ne suffit pas.
    sud = emission("radio:s", "L'invité politique Sud Radio", "2026-10-14T08:30:00+02:00", "radio", "Sud Radio", [])
    agenda = emission("web:s", "Sébastien Chenu sur Sud Radio", "2026-10-14T08:30:00+02:00", "web", "Sud Radio", [])
    assert len(fusion.fusionner([sud, agenda])) == 2


def test_titres():
    assert fusion.meme_titre("Face à face", "FACE À FACE")
    assert fusion.meme_titre("Meeting de Jean-Luc Mélenchon à Clermont-Ferrand",
                             "Meeting de Jean-Luc Mélenchon à Clermont-Ferrand - Vélotypie et LSF")
    assert fusion.meme_titre("Franc-jeu", "Franc-jeu — Gabriel Attal")
    # Un seul mot significatif ne suffit pas (« Le journal » / « Le journal de l'économie »).
    assert not fusion.meme_titre("Le journal", "Le journal de l'économie")
    assert not fusion.meme_titre("Questions au gouvernement", "Questions politiques")


def test_precision_des_versions():
    a = emission("youtube:5", "Meeting de Jean-Luc Mélenchon à Clermont-Ferrand", "2027-03-28T15:00:00+02:00",
                 "youtube", "Jean-Luc Mélenchon", ["https://www.youtube.com/watch?v=a"])
    b = emission("youtube:6", "Meeting de Jean-Luc Mélenchon à Clermont-Ferrand - Vélotypie et LSF",
                 "2027-03-28T15:00:00+02:00", "youtube", "La France insoumise", ["https://www.youtube.com/watch?v=b"])
    (f,) = fusion.fusionner([b, a])
    assert [(s["chaine"], s["precision"]) for s in f["sources"]] == [
        ("Jean-Luc Mélenchon", ""), ("La France insoumise", "Vélotypie et LSF")]
    # Sans séparateur, la suite du titre n'est pas une version particulière.
    assert fusion.precision("Questions au Gouvernement à l'Assemblée", "Questions au gouvernement") == ""
    assert fusion.precision("Face à face (rediffusion)", "Face à face") == "rediffusion"


def test_invites_et_filtre_reunis():
    a = emission("tv:1", "Franc-jeu", "2027-03-28T13:20:00+02:00", "tv", "France 2", [], invites=[])
    b = emission("youtube:4", "Franc-jeu avec Gabriel Attal", "2027-03-28T13:21:00+02:00", "youtube", "franceinfo",
                 ["https://www.youtube.com/watch?v=x"], invites=["Gabriel Attal"], filtre="mots-clés")
    (f,) = fusion.fusionner([a, b])
    assert f["chaine"] == "France 2" and f["invites"] == ["Gabriel Attal"] and f["filtre"] == "liste blanche"


def test_page_et_email(tmp_path):
    connexion = db.ouvrir(tmp_path / "g.sqlite")
    maintenant = datetime(2027, 3, 30, 9, 0, tzinfo=PARIS)
    for e in (LCP, BACKSEAT, DEBRIEF):
        plateforme = e["plateforme"]
        db.enregistrer_collecte(connexion, [e], plateforme, set(), maintenant)
    conf = charger()
    donnees = page.donnees(connexion, conf, maintenant)
    assert len(donnees["emissions"]) == 2
    assert donnees["emissions"][0]["sources"][1]["chaine"] == "BackSeat (Jean Massiet)"
    c = courriel.contenu(connexion, conf, maintenant)
    assert len(c["aujourdhui"]) == 2
    assert "LCP / Public Sénat (TV), BackSeat (Jean Massiet) (Twitch)" in courriel.texte(c)
    assert "Aussi sur" in courriel.page_html(c) and "https://www.twitch.tv/jeanmassiet" in courriel.page_html(c)
    connexion.close()
