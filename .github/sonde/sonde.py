"""Sonde temporaire : HTML brut des grilles RTL, Europe 1, Sud Radio, RMC, Radio Classique."""
import re

import requests

EN_TETES = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15", "Accept-Language": "fr-FR,fr;q=0.9"}
PAGES = [("https://www.rtl.fr/grille/13-10-2026", ["07h00", "07h40", "RTL Matin"]),
         ("https://www.europe1.fr/grille-des-programmes", ["08h10", "La Grande interview"]),
         ("https://www.sudradio.fr/programmes", ["lundi 12 octobre", "08H"]),
         ("https://rmc.bfmtv.com/grille-radio/", ["Apolline", "08h", "8h"]),
         ("https://www.radioclassique.fr/grille-des-programmes/", ["Guillaume Durand", "08h", "8h"])]

for url, reperes in PAGES:
    print("=" * 90)
    r = requests.get(url, headers=EN_TETES, timeout=25)
    r.encoding = "utf-8"
    h = re.sub(r"(?is)<svg.*?</svg>", "", r.text)
    print(url, r.status_code, r.url, len(h))
    for bloc in re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', h)[:2]:
        print("  JSON-LD :", bloc.strip()[:1200])
    for m in re.finditer(r'(?is)<script[^>]*>\s*(window\.__[A-Z_]+__\s*=.{0,600})', h):
        print("  ÉTAT JS :", m.group(1)[:600])
    for repere in reperes:
        i = h.find(repere)
        print(f"--- « {repere} » : position {i} ---")
        if i >= 0:
            print(re.sub(r"\n\s*\n+", "\n", h[max(0, i - 2500): i + 2500]))
            break
