"""TEMPORAIRE : réponses brutes (épisode complet et extrait de Gaspard G, épisode d'Agathe) pour le test."""
import json, os
import requests
from grille.acces import YOUTUBE_API

cle = os.environ["YOUTUBE_API_KEY"]
r = requests.get(f"{YOUTUBE_API}/videos", params={"part": "snippet,liveStreamingDetails,contentDetails",
                 "id": "BruJBhcIdKI,V_b0En7ceyo,csnIz_lEiYA", "key": cle}, timeout=30).json()
for v in r["items"]:
    v["snippet"].pop("thumbnails", None); v["snippet"].pop("localized", None); v["snippet"].pop("tags", None)
    v["snippet"]["description"] = v["snippet"].get("description", "")[:300]
print("VIDEOS", json.dumps(r, ensure_ascii=False))
