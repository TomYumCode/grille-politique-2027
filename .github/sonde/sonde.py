"""Sonde temporaire : quels sites de chaînes annoncent leurs invités à l'avance ?"""
import html
import re

import requests

EN_TETES = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15", "Accept-Language": "fr-FR,fr;q=0.9"}
ADRESSES = [
    "https://www.bfmtv.com/replay-emissions/l-interview/",
    "https://www.bfmtv.com/politique/",
    "https://www.rtl.fr/programmes/l-invite-de-7h40",
    "https://www.rtl.fr/programmes/le-grand-jury",
    "https://www.europe1.fr/emissions/la-grande-interview-europe-1-cnews",
    "https://www.publicsenat.fr/programme-tv",
    "https://lcp.fr/programmes",
    "https://www.lci.fr/programme-tv/",
    "https://www.tf1info.fr/politique/",
    "https://www.cnews.fr/grille-des-programmes",
    "https://www.sudradio.fr/emission/linvite-politique-sud-radio/",
    "https://www.franceinter.fr/emissions/l-invite-de-8h20-le-grand-entretien",
    "https://www.francetvinfo.fr/politique/",
]
DATES = r"(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|demain|ce soir|ce matin|\d{1,2} octobre)"


def texte(h):
    h = re.sub(r"(?is)<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", h)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", h)).split())


for adresse in ADRESSES:
    try:
        r = requests.get(adresse, headers=EN_TETES, timeout=30)
    except requests.RequestException as e:
        print("=====", adresse, "ERREUR", type(e).__name__)
        continue
    t = texte(r.text)
    print("=====", adresse, r.status_code, r.url, len(r.text), "| « invit » :", len(re.findall(r"invit", t, re.I)))
    vus = 0
    for m in re.finditer(r"invit", t, re.I):
        extrait = t[max(0, m.start() - 140): m.start() + 160]
        if re.search(DATES, extrait, re.I):
            print("   ·", extrait)
            vus += 1
            if vus >= 6:
                break
