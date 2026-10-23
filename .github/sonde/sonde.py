"""TEMPORAIRE : morceaux utiles de la page du direct de France 5 (données structurées, titre)."""
import json
import re
import requests
from grille.tv import EN_TETES

t = requests.get("https://www.france.tv/france-5/direct.html", headers=EN_TETES, timeout=30).text
print("TAILLE", len(t))
for bloc in re.findall(r'(?s)<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', t):
    print("LDJSON", bloc[:6000])
for h in re.findall(r"(?s)<h2>.*?</h2>", t)[:2]:
    print("H2", h[:1500])
i = t.find('programTitle')
print("PROGRAMTITLE", t[max(0, i - 2500):i + 600] if i >= 0 else "absent")
i = t.find('dQmdkp')
print("DESCRIPTION", t[max(0, i - 200):i + 2500] if i >= 0 else "absent")
