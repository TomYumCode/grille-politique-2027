"""TEMPORAIRE : le guide XMLTV annonce-t-il l'allocution d'Emmanuel Macron (18 octobre, 20 h) ?"""
import gzip
import xml.etree.ElementTree as ET
import requests
from grille.acces import XMLTV_TNT

r = requests.get(XMLTV_TNT, timeout=60)
print("HTTP", r.status_code, r.headers.get("last-modified"))
racine = ET.fromstring(gzip.decompress(r.content))
CHAINES = {"TF1.fr", "France2.fr", "France3.fr", "BFMTV.fr", "LCI.fr", "CNews.fr", "FranceInfo.fr", "M6.fr",
           "LaChaineParlementaire.fr", "France5.fr"}
for p in racine.iter("programme"):
    if p.get("channel") in CHAINES and p.get("start", "").startswith("20261018") and "1900" <= p.get("start")[8:12] <= "2100":
        titre = p.findtext("title") or ""
        sous = p.findtext("sub-title") or ""
        desc = (p.findtext("desc") or "")[:150]
        print(p.get("channel"), p.get("start")[8:12], p.get("stop")[8:12], "|", titre, "|", sous, "|", desc)
for p in racine.iter("programme"):
    texte = " ".join(filter(None, [p.findtext("title"), p.findtext("sub-title"), p.findtext("desc")]))
    if any(m in texte.lower() for m in ("allocution", "macron", "adresse aux fran", "président de la république s")):
        print("MOT", p.get("channel"), p.get("start"), "|", p.findtext("title"), "|", (p.findtext("desc") or "")[:120])
