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
                if any(m in p["snippet"]["title"].lower() for m in ("candidat", "dossier", "politi", "2027")):
                    print("  LISTE", p["id"], "|", p["snippet"]["title"], "|", p["contentDetails"]["itemCount"])
            jeton = r.get("nextPageToken")
            if not jeton:
                break
for cid in ("UCO6K_kkdP-lnSCiO3tPx7WA",):
    pass
up = api("channels", part="contentDetails", forHandle="@GaspardG")["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
it = api("playlistItems", part="contentDetails", playlistId=up, maxResults=6)
ids = ",".join(i["contentDetails"]["videoId"] for i in it["items"])
for v in api("videos", part="snippet,liveStreamingDetails", id=ids)["items"]:
    print("GASPARD", v["id"], v["snippet"]["publishedAt"], v["snippet"]["liveBroadcastContent"], "live" if v.get("liveStreamingDetails") else "-", "|", v["snippet"]["title"])
