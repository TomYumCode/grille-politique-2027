"""Sonde temporaire : textes des conditions d'utilisation des sources."""
import html
import re

import requests

EN_TETES = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15", "Accept-Language": "fr-FR,fr;q=0.9"}
PAGES = [
    ("https://forum.ouvre-boite.org/t/api-radio-france/398.json", r"proxy|stock|commercial|cache|interm|redistrib|mention|source|directement"),
    ("https://www.radiofrance.com/lopen-api-radio-france", r"proxy|stock|commercial|cache|agr[ée]g|condition|interdit|mention|directement|usage"),
    ("https://developers.radiofrance.fr/", r"condition|cgu|commercial|proxy|stock|cache|mention"),
    ("https://developers.radiofrance.fr/doc/cgu", r"."),
    ("https://developers.google.com/youtube/terms/developer-policies", r"30 calendar days|privacy policy|Store|refresh|attribut|branding|brand"),
    ("https://www.twitch.tv/p/en/legal/developer-agreement/", r"24 hours|cache|store|commercial|monetiz|attribut"),
    ("https://xmltvfr.fr/", r"licen|condition|utilis|gratuit|commercial|redistrib"),
]


def texte(h):
    h = re.sub(r"(?is)<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", h)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", h)).split())


for url, motif in PAGES:
    try:
        r = requests.get(url, headers=EN_TETES, timeout=30)
    except requests.RequestException as e:
        print("=====", url, "ERREUR", type(e).__name__)
        continue
    t = texte(r.text.replace("\\n", " ").replace("\\u003c", "<").replace("\\u003e", ">"))
    print("=====", url, r.status_code, r.url, len(t))
    vus = 0
    for phrase in re.split(r"(?<=[.!?])\s+", t):
        if re.search(motif, phrase, re.I) and 20 < len(phrase) < 700:
            print("   ·", phrase)
            vus += 1
            if vus >= 25:
                break
