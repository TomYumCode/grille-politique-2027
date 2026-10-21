"""TEMPORAIRE : que dit le guide XMLTV de BFMTV ce soir (Natacha Polony en direct) ?"""
import gzip
import xml.etree.ElementTree as ET
import requests
from grille.acces import XMLTV_TNT

r = requests.get(XMLTV_TNT, timeout=60)
print("HTTP", r.status_code, r.headers.get("last-modified"))
racine = ET.fromstring(gzip.decompress(r.content))
for p in racine.iter("programme"):
    debut = p.get("start", "")
    if p.get("channel") == "BFMTV.fr" and "20261021" <= debut[:8] <= "20261026":
        print(debut[:12], p.get("stop", "")[8:12], "|", p.findtext("title"), "|", p.findtext("sub-title") or "", "|",
              " ".join((p.findtext("desc") or "").split())[:300], "|", [c.text for c in p.findall("category")])
