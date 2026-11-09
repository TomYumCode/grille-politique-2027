"""TEMPORAIRE : quels flux RSS politiques et médias répondent, et que contiennent-ils ?"""
import re
import xml.etree.ElementTree as ET
import requests

FLUX = [
    "https://www.francetvinfo.fr/politique.rss",
    "https://www.francetvinfo.fr/titres.rss",
    "https://www.lemonde.fr/politique/rss_full.xml",
    "https://www.lefigaro.fr/rss/figaro_politique.xml",
    "https://www.liberation.fr/arc/outboundfeeds/rss/category/politique/?outputType=xml",
    "https://www.bfmtv.com/rss/politique/",
    "https://www.bfmtv.com/rss/news-24-7/",
    "https://www.tf1info.fr/politique/rss.xml",
    "https://www.tf1info.fr/feeds/rss-une.xml",
    "https://www.20minutes.fr/feeds/rss-politique.xml",
    "https://feeds.leparisien.fr/leparisien/rss/politique",
    "https://www.europe1.fr/rss/politique.xml",
    "https://www.lexpress.fr/arc/outboundfeeds/rss/politique.xml",
    "https://www.huffingtonpost.fr/politique/rss_headline.xml",
    "https://www.publicsenat.fr/rss.xml",
    "https://www.publicsenat.fr/feed",
    "https://lcp.fr/rss.xml",
    "https://www.lejdd.fr/rss/politique.xml",
    "https://www.ouest-france.fr/rss/une",
    "https://www.lepoint.fr/politique/rss.xml",
    "https://www.nouvelobs.com/politique/rss.xml",
    "https://www.marianne.net/rss.xml",
    "https://www.rtl.fr/actu/politique/rss",
    "https://rmc.bfmtv.com/rss/actualites/politique/",
    "https://www.cnews.fr/rss/categorie/politique",
    "https://www.lci.fr/politique/rss.xml",
    "https://www.ozap.com/rss",
    "https://www.ozap.com/rss/news",
    "https://www.puremedias.com/rss",
    "https://stephanelarue.com/feed/",
    "https://www.programme-tv.net/rss/news.xml",
    "https://www.telestar.fr/rss",
    "https://www.radiofrance.fr/franceinter/rss",
]
EN_TETES = {"User-Agent": "Mozilla/5.0 (compatible; grille-politique-2027; essai de flux RSS)"}
for url in FLUX:
    try:
        r = requests.get(url, headers=EN_TETES, timeout=20)
    except requests.RequestException as e:
        print(f"ERREUR {url} : {type(e).__name__}")
        continue
    texte = r.text
    nb = len(re.findall(r"<item[\s>]", texte)) + len(re.findall(r"<entry[\s>]", texte))
    titres, dates = [], []
    try:
        racine = ET.fromstring(r.content)
        for it in racine.iter():
            if it.tag.split("}")[-1] in ("item", "entry"):
                t = next((c.text for c in it if c.tag.split("}")[-1] == "title"), "") or ""
                d = next((c.text for c in it if c.tag.split("}")[-1] in ("pubDate", "published", "updated", "date")), "") or ""
                titres.append(t.strip()[:90]); dates.append(d.strip()[:31])
        xml_ok = "xml ok"
    except ET.ParseError as e:
        xml_ok = f"xml illisible ({e})"
    print(f"\n{r.status_code} {url} [{r.headers.get('content-type','')[:40]}] {nb} articles, {xml_ok}, final {r.url[:80]}")
    for t, d in list(zip(titres, dates))[:3]:
        print(f"   {d} | {t}")
