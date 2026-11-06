"""TEMPORAIRE : listes de lecture des séries politiques (Les Dossiers, Dans les yeux d'Agathe, Les aspirants)."""
import json, os
import requests
from grille.acces import YOUTUBE_API

cle = os.environ["YOUTUBE_API_KEY"]
S = requests.Session()
def api(chemin, **p):
    r = S.get(f"{YOUTUBE_API}/{chemin}", params={**p, "key": cle}, timeout=30)
    r.raise_for_status()
    return r.json()

for poignee, mots in (("@GaspardG", ["dossier"]), ("@franceinfo", ["agathe", "yeux"]), ("@rtl_france", ["aspirant"]),
                      ("@TF1INFO", ["dossier", "gaspard"])):
    canal = api("channels", part="id,contentDetails", forHandle=poignee)["items"][0]
    print("=====", poignee, canal["id"])
    jeton = None
    for _ in range(6):
        d = api("playlists", part="snippet,contentDetails", channelId=canal["id"], maxResults=50, **({"pageToken": jeton} if jeton else {}))
        for p in d.get("items", []):
            t = p["snippet"]["title"]
            if any(m in t.lower() for m in mots):
                print("  LISTE", p["id"], "|", t, "|", p["contentDetails"]["itemCount"], "vidéos")
        jeton = d.get("nextPageToken")
        if not jeton:
            break
# Exemple de réponse pour le test : les 3 derniers éléments de la liste trouvée pour Gaspard G, et leurs détails.
