"""Sonde temporaire : extraits réels des grilles RMC et Radio Classique pour les tests."""
import re

import requests

EN_TETES = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15", "Accept-Language": "fr-FR,fr;q=0.9"}


def leger(h):
    h = re.sub(r"(?is)<(svg|picture|script|style|noscript)[^>]*>.*?</\1>|<(img|source|link|meta)[^>]*>|<!--.*?-->", "", h)
    return re.sub(r"\s*\n\s*", "\n", h)


def extrait(nom, texte):
    print(f"<<<EXTRAIT {nom}>>>")
    print(texte)
    print(f"<<<FIN {nom}>>>")


h = requests.get("https://rmc.bfmtv.com/grille-radio/", headers=EN_TETES, timeout=30).text
debut = h.find("grille_days")
fin = h.rfind("grille_hours_content")
print("RMC jours", re.findall(r'(?s)class="day_title[^"]*"[^>]*>(.*?)<', h)[:20])
extrait("rmc", leger(h[max(0, h.rfind("<", 0, debut)):h.find("</article>", fin) + 10]))
h = requests.get("https://www.radioclassique.fr/grille-des-programmes/2026-10-13/", headers=EN_TETES, timeout=30).text
debut = h.find("timeline__block__row--headline")
fin = h.rfind("timeline__block__row")
extrait("radioclassique", leger(h[max(0, h.rfind("<div", 0, debut)):h.find("<!-- .timeline__block__row -->", fin) + 40]))
