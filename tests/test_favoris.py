"""Règles des favoris (grille/modele_page/favoris.js), exécutées avec Node si présent."""

import json
import shutil
import subprocess

import pytest

from grille import page

NODE = shutil.which("node")

SCRIPT = """
require(process.argv[1]);
const F = globalThis.Favoris;
const qag = {id: "tv:1", titre: "C politique S18", chaine: "France 5", invites: ["Jordan Bardella"], campagne: ""};
const qs = {id: "radio:2", titre: "Questions du soir : le débat — Glucksmann candidat ?", chaine: "France Culture",
            invites: [], campagne: "candidat dans le titre"};
const fav = F.vides();
const resultats = {vide: [F.raisons(qag, fav), F.raisons(qs, fav)]};
F.basculer(fav.personnes, "Jordan Bardella");
F.basculer(fav.emissions, {cle: F.cleEmission(qs), titre: F.nomEmission(qs)}, (a, b) => a.cle === b.cle);
resultats.suivis = [F.raisons(qag, fav), F.raisons(qs, fav)];
resultats.saison = F.cleEmission({titre: "C politique S19", chaine: "France 5"}) === F.cleEmission(qag);
fav.presidentielle = true;
F.basculer(fav.personnes, "Jordan Bardella");  // second appui : retiré
resultats.presidentielle = [F.raisons(qag, fav), F.raisons(qs, fav)];
console.log(JSON.stringify(resultats));
"""


@pytest.mark.skipif(NODE is None, reason="Node absent")
def test_raisons_d_un_favori():
    sortie = subprocess.run([NODE, "-e", SCRIPT, str(page.MODELE / "favoris.js")], capture_output=True, text=True,
                            check=True).stdout
    r = json.loads(sortie)
    assert r["vide"] == [[], []]
    assert r["suivis"] == [["Jordan Bardella"], ["« Questions du soir : le débat »"]]
    assert r["saison"] is True  # « C politique S18 » et « S19 » : la même émission
    assert r["presidentielle"] == [[], ["« Questions du soir : le débat »", "Présidentielle 2027"]]
