"""Sonde temporaire : collecteur des radios privées sur les vrais sites, et extraits pour les tests."""
import re
import subprocess
import sys

import requests

EN_TETES = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15", "Accept-Language": "fr-FR,fr;q=0.9"}


def leger(h):
    return re.sub(r"(?is)<(svg|picture|script|style)[^>]*>.*?</\1>|<(img|source)[^>]*>", "", h)


def extrait(nom, texte):
    print(f"<<<EXTRAIT {nom}>>>")
    print(texte)
    print(f"<<<FIN {nom}>>>")


h = requests.get("https://www.rtl.fr/grille/13-10-2026", headers=EN_TETES, timeout=30).text
cartes = re.split(r'(?=<div class="programme-card[ "])', h)
garde = [c for c in cartes[1:] if re.search(r"programme-card__title[^>]*>(RTL Matin|RTL Soir|Un jour, une vie)<", c)]
extrait("rtl", leger("".join(garde))[:60000])
h = requests.get("https://www.europe1.fr/grille-des-programmes", headers=EN_TETES, timeout=30).text
i, j = h.find('id="panel-lundi"'), h.find('id="panel-mardi"')
k = h.find("09h00 - 11h00", j)
extrait("europe1", leger("<section\n" + h[i:k])[:60000])
h = requests.get("https://www.sudradio.fr/programmes", headers=EN_TETES, timeout=30).text
i = h.find('<h2 class="sud_planning_titre_jour">')
lignes = re.split(r'(?=<li class="sud_planning_ligne)', h[i:])
extrait("sudradio", leger(lignes[0][:400] + "".join(lignes[2:4]))[:60000])
sys.stdout.flush()
# En dernier : le journal ne garde que la fin de la sortie.
subprocess.run([sys.executable, "-m", "grille", "--base", "/tmp/sonde.sqlite", "collecter-radio", "--motifs"])
subprocess.run([sys.executable, "-m", "grille", "--base", "/tmp/sonde.sqlite", "douteux", "--nombre", "60"])
