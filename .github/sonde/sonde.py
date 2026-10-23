"""TEMPORAIRE : le lecteur des pages du direct (grille/directs.py) sur les vraies pages."""
from datetime import datetime
from pathlib import Path
import requests
from grille import config, db, directs
from grille.tv import PARIS

conf = config.charger()
c = db.ouvrir(Path("/tmp/essai.sqlite"))
for url in ("https://www.france.tv/france-2/direct.html", "https://www.france.tv/france-3/direct.html",
            "https://www.france.tv/france-5/direct.html"):
    e = directs.lire_page(requests.get(url, headers={"User-Agent": "grille-politique-2027 (usage personnel)"}, timeout=30).text)
    print(url, "->", e and {k: (v.isoformat() if hasattr(v, "isoformat") else v[:120]) for k, v in e.items()})
r = directs.collecter(conf, requests.Session(), c, datetime.now(PARIS))
print("RAPPORT pages", r.pages_lues, "illisibles", r.illisibles, "anomalies", r.anomalies, "interrompu", r.interrompu)
for e in r.retenues:
    print("RETENUE", e["titre"], e["debut"], e["motif"], e["invites"], e["cites"])
