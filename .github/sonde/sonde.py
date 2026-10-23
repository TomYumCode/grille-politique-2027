"""TEMPORAIRE : vers 18 h, france.tv annonce-t-il déjà les sujets de la soirée ?"""
import re
import requests
from grille.tv import EN_TETES

def propre(x):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x)).replace("\\u0026", "&").strip()

for url in ["https://www.france.tv/france-5/direct.html", "https://www.france.tv/france-2/direct.html"]:
    t = requests.get(url, headers=EN_TETES, timeout=30).text
    print("=====", url, len(t))
    # Titres de programme : <h2>…</h2>, et tout ce qui ressemble à un horaire « 22h45 » ou « 22:45 » près d'un titre.
    for h in re.findall(r"(?s)<h2>(.*?)</h2>", t)[:6]:
        print("  h2:", propre(h)[:160])
    for nom in ["C ce soir", "C dans l", "C à vous", "C l'hebdo", "Quelle époque", "20h30"]:
        n = [m.start() for m in re.finditer(re.escape(nom), t)]
        print(f"  « {nom} » : {len(n)} occurrences")
        for i in n[:3]:
            print("     ", propre(t[max(0, i - 200):i + 400])[:420])
    heures = re.findall(r'(?:"(?:startDate|start|begin|broadcastBeginDate|beginDate|diffusionDate)[^"]*"\s*:\s*"[^"]+")', t)
    print("  champs d'horaire :", heures[:15])
