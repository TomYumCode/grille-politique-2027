"""TEMPORAIRE : que disent le guide et le site de LCI de l'émission de ce soir (Polony, Odoul) ?"""
import gzip, re
import xml.etree.ElementTree as ET
import requests
from grille.acces import XMLTV_TNT

r = requests.get(XMLTV_TNT, timeout=60)
print("GUIDE", r.headers.get("last-modified"))
for p in ET.fromstring(gzip.decompress(r.content)).iter("programme"):
    if p.get("channel") == "LCI.fr" and p.get("start", "").startswith("20261025"):
        print(p.get("start")[8:12], p.get("stop")[8:12], "|", p.findtext("title"), "|", p.findtext("sub-title") or "", "|",
              " ".join((p.findtext("desc") or "").split())[:300])
NAV = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"}
for url in ["https://www.tf1.fr/lci/direct", "https://www.tf1info.fr/direct/", "https://www.lci.fr/direct/",
            "https://www.tf1info.fr/emissions/"]:
    try:
        t = requests.get(url, headers=NAV, timeout=30)
    except Exception as e:
        print("=====", url, "ERREUR", e); continue
    print("=====", url, t.status_code, t.url, len(t.text))
    for mot in ("Polony", "Odoul", "invité", "En ce moment"):
        for m in list(re.finditer(mot, t.text))[:2]:
            print(f"  [{mot}]", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t.text[max(0, m.start() - 250):m.end() + 250]))[:400])
    for bloc in re.findall(r'(?s)<script[^>]*application/ld\+json[^>]*>(.*?)</script>', t.text)[:3]:
        print("  LDJSON", bloc[:700])
