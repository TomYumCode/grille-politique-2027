"""TEMPORAIRE : chaînes à suivre en entier (« toutes ») : vidéos longues et décision du filtre."""
import os
import requests
from grille.acces import YOUTUBE_API
from grille.config import charger
from grille.filtre import FiltrePolitique
from grille.youtube import duree_iso

cle = os.environ["YOUTUBE_API_KEY"]
config = charger()
filtre = FiltrePolitique(config)
par_nom = {c.nom: c for c in config.chaines}

def api(point, **p):
    return requests.get(f"{YOUTUBE_API}/{point}", params={**p, "key": cle}, timeout=30).json()

cibles = [("handle", h) for h in ["HugoDecrypte", "HugoDecrypteGrandsFormats", "HugoDecrypteLesGrandsFormats",
                                  "thinkerview", "konbini", "BrutFR", "LEGENDmedia"]]
cibles.append(("id", "UCAcAnMF0OrCtUep3Y4M-ZPw"))
for genre, valeur in cibles:
    p = {"forHandle": valeur} if genre == "handle" else {"id": valeur}
    r = api("channels", part="snippet,contentDetails", **p)
    for ch in r.get("items") or []:
        print(f"\n=== {valeur} -> {ch['id']} « {ch['snippet']['title']} » {ch['snippet'].get('customUrl')}")
        items = api("playlistItems", part="contentDetails", maxResults=50,
                    playlistId=ch["contentDetails"]["relatedPlaylists"]["uploads"]).get("items") or []
        ids = [it["contentDetails"]["videoId"] for it in items]
        videos = api("videos", part="snippet,contentDetails,liveStreamingDetails", id=",".join(ids)).get("items") or []
        chaine = next((c for c in config.chaines if c.plateforme == "youtube" and
                       (valeur.lower() in c.adresse.lower())), None) or par_nom["Konbini"]
        for v in videos:
            d = duree_iso(v["contentDetails"].get("duration"))
            longue = d is not None and d.total_seconds() >= 1200
            dec = filtre.decider(chaine, v["snippet"]["title"], v["snippet"].get("description", "")) if longue else None
            print(f"{v['snippet']['publishedAt'][:16]} {str(d):>8} {'DIRECT' if v.get('liveStreamingDetails') else '      '}"
                  f" {'RETENU' if dec else ('  -   ' if longue else ' court')} {v['id']} {v['snippet']['title'][:90]}"
                  + (f"  [{dec.categorie} {dec.invites}]" if dec else ""))
    if not r.get("items"):
        print(f"\n=== {valeur} : introuvable")
r = api("search", part="snippet", q="HugoDécrypte Emmanuel Macron interview", type="video",
        publishedAfter="2026-10-20T00:00:00Z", maxResults=10)
print("\n=== recherche Macron")
for it in r.get("items") or []:
    print(it["snippet"]["publishedAt"][:16], it["id"]["videoId"], it["snippet"]["channelId"],
          it["snippet"]["channelTitle"], "|", it["snippet"]["title"][:90])
