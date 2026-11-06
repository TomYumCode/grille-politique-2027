"""TEMPORAIRE : séries supplémentaires et réponses enregistrées pour le test des épisodes."""
import json, os
import requests
from grille.acces import YOUTUBE_API

cle = os.environ["YOUTUBE_API_KEY"]
S = requests.Session()
def api(chemin, **p):
    r = S.get(f"{YOUTUBE_API}/{chemin}", params={**p, "key": cle}, timeout=30)
    r.raise_for_status()
    return r.json()

d = api("playlists", part="snippet,contentDetails", id="PLOInMnMM0_fcA_TQw8cdc54Oen0HnUIH4")
for p in d.get("items", []):
    print("POURQUOI", p["id"], "|", p["snippet"]["title"], "|", p["snippet"]["channelTitle"], p["snippet"]["channelId"], "|", p["contentDetails"]["itemCount"])
for poignee in ("@SamZirah", "@samzirah", "@SamZirahOfficiel"):
    try:
        items = api("channels", part="id,snippet", forHandle=poignee).get("items", [])
    except Exception as e:
        items = []
    for c in items:
        print("ZIRAH", poignee, c["id"], c["snippet"]["title"])
        jeton = None
        for _ in range(4):
            r = api("playlists", part="snippet,contentDetails", channelId=c["id"], maxResults=50, **({"pageToken": jeton} if jeton else {}))
            for p in r.get("items", []):
                print("  LISTE", p["id"], "|", p["snippet"]["title"], "|", p["contentDetails"]["itemCount"])
            jeton = r.get("nextPageToken")
            if not jeton:
                break
# Réponses à enregistrer : 3 derniers éléments de la liste d'Agathe et détails des vidéos.
items = api("playlistItems", part="contentDetails", playlistId="PLg6GanYvTasXMpDNnfw4fDbaSCj_X0jeR", maxResults=3)
print("PLAYLISTITEMS", json.dumps(items, ensure_ascii=False))
ids = ",".join(i["contentDetails"]["videoId"] for i in items["items"])
videos = api("videos", part="snippet,liveStreamingDetails", id=ids)
for v in videos["items"]:
    v["snippet"].pop("thumbnails", None); v["snippet"]["description"] = v["snippet"].get("description", "")[:400]
    v["snippet"].pop("localized", None); v["snippet"].pop("tags", None)
print("VIDEOS", json.dumps(videos, ensure_ascii=False))
