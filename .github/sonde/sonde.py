"""TEMPORAIRE : articles complets annonçant une candidature (réponses enregistrées des tests)."""
import re
import requests

EN_TETES = {"User-Agent": "Mozilla/5.0 (compatible; grille-politique-2027; mesure de flux RSS)"}
for url in ["https://www.publicsenat.fr/feed", "https://www.20minutes.fr/feeds/rss-politique.xml",
            "https://feeds.leparisien.fr/leparisien/rss/politique"]:
    texte = requests.get(url, headers=EN_TETES, timeout=20).text
    tete = texte[:texte.index("<item")]
    items = re.findall(r"<item[\s>].*?</item>", texte, re.S)
    choisis = [i for i in items if re.search(r"(?i)candidat|course à l|élysée", i)][:4] + items[:2]
    print("=====", url)
    print(tete)
    for i in choisis:
        i = re.sub(r"<content:encoded>.*?</content:encoded>", "", i, flags=re.S)
        print(i)
    print("===== fin")
