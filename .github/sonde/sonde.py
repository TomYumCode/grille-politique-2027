"""Sonde temporaire : structure des grilles RMC et Radio Classique."""
import collections
import re

import requests

EN_TETES = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15", "Accept-Language": "fr-FR,fr;q=0.9"}


def leger(h):
    return re.sub(r"(?is)<(svg|picture|script|style|noscript)[^>]*>.*?</\1>|<(img|source|link|meta)[^>]*>", "", h)


for adresse in ("https://rmc.bfmtv.com/grille-radio/", "https://www.radioclassique.fr/grille-des-programmes/",
                "https://www.radioclassique.fr/grille-des-programmes/mardi/"):
    print(f"===== {adresse}")
    try:
        r = requests.get(adresse, headers=EN_TETES, timeout=30)
    except requests.RequestException as e:
        print("ERREUR", e)
        continue
    h = r.text
    print("statut", r.status_code, "url finale", r.url, "taille", len(h))
    print("json-ld", len(re.findall(r"application/ld\+json", h)), "__NEXT_DATA__", "__NEXT_DATA__" in h,
          "nuxt", "__NUXT" in h)
    classes = collections.Counter(c for attr in re.findall(r'class="([^"]+)"', h) for c in attr.split())
    print("classes", [c for c, n in classes.most_common(80)])
    liens = sorted(set(re.findall(r'href="([^"]*(?:grille|programme)[^"]*)"', h)))[:30]
    print("liens grille", liens)
    corps = leger(h)
    heures = [m.start() for m in re.finditer(r"\b\d{1,2}[h:]\d{2}\b", corps)]
    print("heures trouvées", len(heures))
    if heures:
        debut = max(0, heures[min(5, len(heures) - 1)] - 1500)
        print("<<<EXTRAIT>>>")
        print(re.sub(r"\n\s*\n+", "\n", corps[debut:debut + 7000]))
        print("<<<FIN>>>")
