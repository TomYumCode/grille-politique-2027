"""TEMPORAIRE : extraits bruts de deux flux (RSS 2.0) pour les réponses enregistrées des tests."""
import re
import requests

EN_TETES = {"User-Agent": "Mozilla/5.0 (compatible; grille-politique-2027; mesure de flux RSS)"}
for url in ["https://www.tf1info.fr/feeds/rss-une.xml", "https://lcp.fr/rss-actualites.xml"]:
    texte = requests.get(url, headers=EN_TETES, timeout=20).text
    debut = texte.index("<item")
    tete = texte[:debut]
    items = re.findall(r"<item[\s>].*?</item>", texte, re.S)
    # Les trois premiers articles, plus ceux qui parlent d'un invité.
    choisis = items[:3] + [i for i in items[3:] if re.search(r"(?i)invit", i)][:3]
    print("=====", url)
    print(tete[-1500:] if len(tete) > 1500 else tete)
    for i in choisis:
        print(i[:2500])
    print("===== fin")
