"""Sonde temporaire : grilles des radios privées (RTL, Europe 1, RMC, Sud Radio, Radio Nova…)."""
import re

import requests

EN_TETES = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15", "Accept-Language": "fr-FR,fr;q=0.9"}
ACCUEILS = ["https://www.rtl.fr/", "https://www.europe1.fr/", "https://rmc.bfmtv.com/", "https://www.sudradio.fr/",
            "https://www.nova.fr/", "https://www.franceinfo.fr/", "https://www.radioclassique.fr/",
            "https://www.bfmtv.com/economie/replay-emissions/", "https://www.rfi.fr/fr/", "https://www.lci.fr/"]
GRILLES = ["https://www.rtl.fr/programmes", "https://www.rtl.fr/grille", "https://www.europe1.fr/programmes",
           "https://www.europe1.fr/grille-des-programmes", "https://rmc.bfmtv.com/grille-programmes/",
           "https://rmc.bfmtv.com/programmes/", "https://www.sudradio.fr/programmes", "https://www.sudradio.fr/grille",
           "https://www.nova.fr/programmes", "https://www.nova.fr/grille", "https://www.radioclassique.fr/programmes/"]
MOTIF = r'href="([^"#]*(?:programme|grille|emission|émission|invite|podcast)[^"]*)"'


def get(url):
    try:
        r = requests.get(url, headers=EN_TETES, timeout=20)
        r.encoding = r.apparent_encoding if r.encoding in (None, "ISO-8859-1") else r.encoding
        return r
    except requests.RequestException as e:
        print("  ERREUR", type(e).__name__, str(e)[:120])


for url in ACCUEILS:
    print("=" * 80, "\n" + url)
    r = get(url)
    if r is None:
        continue
    t = re.search(r"(?is)<title>(.*?)</title>", r.text)
    print(f"  HTTP {r.status_code} → {r.url} ; {(t.group(1).strip()[:80] if t else '-')}")
    print("  liens :", sorted(set(re.findall(MOTIF, r.text, re.I)))[:25])
for url in GRILLES:
    print("=" * 80, "\n" + url)
    r = get(url)
    if r is None:
        continue
    h = r.text
    t = re.search(r"(?is)<title>(.*?)</title>", h)
    print(f"  HTTP {r.status_code} → {r.url} ; {len(h)} car. ; {(t.group(1).strip()[:80] if t else '-')}")
    print("  JSON-LD :", len(re.findall(r"application/ld\+json", h)), "; __NEXT_DATA__ :", "__NEXT_DATA__" in h,
          "; data-page :", "data-page=" in h)
    texte = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style|svg)[^>]*>.*?</\1>", " ", h)))
    heures = list(re.finditer(r"\b\d{1,2}[h:]\d{2}\b", texte))
    print("  heures trouvées :", len(heures))
    if heures:
        i = heures[0].start()
        print("  …", texte[max(0, i - 200): i + 1500])
