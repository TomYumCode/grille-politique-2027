"""Sonde temporaire : extrait réel de la grille Radio Classique pour les tests."""
import re

import requests

EN_TETES = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15", "Accept-Language": "fr-FR,fr;q=0.9"}


def leger(h):
    h = re.sub(r"(?is)<(svg|picture|script|style|noscript)[^>]*>.*?</\1>|<(img|source|link|meta)[^>]*>|<!--.*?-->", "", h)
    return re.sub(r"\s*\n\s*", "\n", h)


for adresse in ("https://www.radioclassique.fr/grille-des-programmes/2026-10-13/",
                "https://www.radioclassique.fr/grille-des-programmes/2026-10-18/"):
    r = requests.get(adresse, headers=EN_TETES, timeout=30)
    h = r.text
    print("=====", adresse, r.status_code, r.url, len(h), h.count("timeline__block__row"), h.count("episode_title"))
    debut = h.find('<div class="timeline__block__row')
    fin = h.rfind('<div class="timeline__block__row')
    fin = h.find("<!-- .timeline__block__row -->", fin)
    print("bornes", debut, fin)
    print("<<<EXTRAIT>>>")
    print(leger(h[debut:fin + 31]))
    print("<<<FIN>>>")
