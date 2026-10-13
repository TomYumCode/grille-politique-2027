"""Sonde temporaire : émissions de Radio Courtoisie par date, programmes de Mediapart."""
import os
import re

import requests

EN_TETES = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15", "Accept-Language": "fr-FR,fr;q=0.9"}


def leger(h):
    h = re.sub(r"(?is)<(svg|picture|script|style|noscript)[^>]*>.*?</\1>|<(img|source|link|meta)[^>]*>|<!--.*?-->", "", h)
    return re.sub(r"\s*\n\s*", "\n", h)


def texte(f):
    return " ".join(re.sub(r"<[^>]+>", " ", f).split())


for adresse in ("https://www.rc.fr/filtres-emissions/filtre-date/", "https://www.mediapart.fr/studio"):
    r = requests.get(adresse, headers=EN_TETES, timeout=30)
    print("=====", adresse, r.status_code, r.url, len(r.text))
    corps = leger(r.text)
    heures = [m.start() for m in re.finditer(r"\b\d{1,2}\s*[hH:]\s*\d{2}\b", corps)]
    print("heures", len(heures))
    print(sorted(set(re.findall(r'href="([^"]*(?:emission|direct|live|programme|agenda|studio|filtre)[^"]*)"', r.text, re.I)))[:40])
    if heures:
        d = max(0, heures[0] - 1500)
        print("<<<EXTRAIT>>>")
        print(corps[d:d + 6000])
        print("<<<FIN>>>")
# Mediapart sur YouTube : dernières vidéos, directs et premières.
cle = os.environ.get("YOUTUBE_API_KEY")
if cle:
    api = "https://www.googleapis.com/youtube/v3"
    c = requests.get(f"{api}/channels", params={"part": "contentDetails", "forHandle": "mediapart", "key": cle}, timeout=30).json()
    uu = c["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    items = requests.get(f"{api}/playlistItems", params={"part": "contentDetails", "playlistId": uu, "maxResults": 50, "key": cle},
                         timeout=30).json()["items"]
    ids = ",".join(i["contentDetails"]["videoId"] for i in items)
    videos = requests.get(f"{api}/videos", params={"part": "snippet,liveStreamingDetails", "id": ids, "key": cle}, timeout=30).json()["items"]
    for v in videos:
        d = v.get("liveStreamingDetails") or {}
        print("MEDIAPART", v["snippet"]["publishedAt"], v["snippet"].get("liveBroadcastContent"),
              d.get("scheduledStartTime") or d.get("actualStartTime") or "-", v["snippet"]["title"][:90])
