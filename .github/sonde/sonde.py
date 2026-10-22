"""TEMPORAIRE : où france.tv publie-t-il le sujet du jour de « C ce soir » ?"""
import re
import requests
from grille.tv import EN_TETES

CLE = "strat"  # « la stratégie de la tension »
for url in ["https://www.france.tv/france-5/direct.html", "https://www.france.tv/france-5/c-ce-soir/",
            "https://www.france.tv/france-5/c-dans-l-air/", "https://www.france.tv/france-5/c-a-vous/",
            "https://www.france.tv/programme-tv/", "https://www.france.tv/france-5/programme-tv/",
            "https://www.francetvpro.fr/france-5/grille-des-programmes"]:
    try:
        r = requests.get(url, headers=EN_TETES, timeout=30)
    except Exception as e:
        print("=====", url, "ERREUR", e); continue
    t = r.text
    print("=====", url, r.status_code, r.url, len(t))
    for m in list(re.finditer(r"(?i)strat[ée]gie de la tension|LFI", t))[:4]:
        print("   ...", re.sub(r"\s+", " ", t[max(0, m.start() - 300):m.end() + 200]))
    # Liens d'épisodes de C ce soir et API éventuelles
    print("   épisodes:", sorted(set(re.findall(r'/france-5/c-ce-soir/[^"\'\s<>]+', t)))[:12])
    print("   api:", sorted(set(re.findall(r'https://[a-z0-9.-]*(?:api|yatta)[a-z0-9.-]*\.[a-z]+/[^"\'\s<>]{0,80}', t)))[:10])
