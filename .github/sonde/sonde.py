"""Sonde temporaire : carte RTL en cours, replays RTL, Radio Courtoisie, Mediapart."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

EN_TETES = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15", "Accept-Language": "fr-FR,fr;q=0.9"}


def leger(h):
    h = re.sub(r"(?is)<(svg|picture|script|style|noscript)[^>]*>.*?</\1>|<(img|source|link|meta)[^>]*>|<!--.*?-->", "", h)
    return re.sub(r"\s*\n\s*", "\n", h)


def texte(f):
    return " ".join(re.sub(r"<[^>]+>", " ", f).split())


aujourdhui = datetime.now(ZoneInfo("Europe/Paris"))
print("heure de Paris", aujourdhui)
h = requests.get(f"https://www.rtl.fr/grille/{aujourdhui:%d-%m-%Y}", headers=EN_TETES, timeout=30).text
cartes = re.split(r'(?=<div class="programme-card[ "])', h)[1:]
print("RTL cartes", len(cartes))
for c in cartes:
    cls = re.match(r'<div class="([^"]*)"', c).group(1)
    t = re.search(r'programme-card__time[^>]*>(.*?)</', c, re.S)
    ti = re.search(r'programme-card__title[^>]*>(.*?)</', c, re.S)
    chron = re.findall(r'(?s)<li class="programme-card__chronique".*?</li>', c)
    print("CARTE", cls, "|", t and texte(t.group(1)), "|", ti and texte(ti.group(1)), "| chroniques", len(chron),
          "| autres li", len(re.findall(r'<li class="([^"]*)"', c)), sorted(set(re.findall(r'<li class="([^"]*)"', c)))[:5])
    for li in chron[:30]:
        print("   CHRON", texte(li)[:120], re.findall(r'href="([^"]+)"', li)[:3])
# Carte du matin en entier, pour voir sa forme
matin = [c for c in cartes if re.search(r'programme-card__title[^>]*>\s*RTL Matin', c)]
if matin:
    print("<<<EXTRAIT rtl_matin>>>")
    print(leger(matin[0])[:20000])
    print("<<<FIN rtl_matin>>>")
for adresse in ("https://www.radiocourtoisie.fr/", "https://www.mediapart.fr/"):
    try:
        r = requests.get(adresse, headers=EN_TETES, timeout=30)
        print("=====", adresse, r.status_code, r.url, len(r.text))
        print(sorted(set(re.findall(r'href="([^"]*(?:grille|programme|emission|direct|studio|agenda|live)[^"]*)"', r.text, re.I)))[:60])
    except requests.RequestException as e:
        print("=====", adresse, "ERREUR", e)
