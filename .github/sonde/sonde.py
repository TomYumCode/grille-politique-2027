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
garde = [c for c in cartes[1:] if re.search(r"programme-card__title[^>]*>(RTL Matin|Un jour, une vie)<", c)]
extrait("rtl", leger("".join(garde))[:60000])
sys.stdout.flush()
# En dernier : le journal ne garde que la fin de la sortie.
subprocess.run([sys.executable, "-m", "grille", "--base", "/tmp/sonde.sqlite", "collecter-radio", "--motifs"])
subprocess.run([sys.executable, "-m", "grille", "--base", "/tmp/sonde.sqlite", "douteux", "--nombre", "60"])
