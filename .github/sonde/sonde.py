"""TEMPORAIRE : quelles adresses de direct l'application France TV reconnaît-elle ?"""
import json
import re
import requests

NAV = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
                     "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"}
r = requests.get("https://www.france.tv/.well-known/apple-app-site-association", headers=NAV, timeout=30)
print("AASA", r.status_code, r.headers.get("content-type"))
print(r.text[:4000])
for url in ["https://www.france.tv/lcp-public-senat/direct.html", "https://www.france.tv/lcp/direct.html",
            "https://www.france.tv/public-senat/direct.html", "https://www.france.tv/france-2/direct.html",
            "https://www.france.tv/directs/", "https://www.france.tv/lcp-public-senat/",
            "https://lcp.fr/direct-lcp-5434", "https://www.publicsenat.fr/direct"]:
    try:
        r = requests.get(url, headers=NAV, timeout=30, allow_redirects=True)
        liens = sorted(set(re.findall(r'href="(/[^"]*direct[^"]*)"', r.text)))[:40]
        print("=====", url, r.status_code, "->", r.url, len(r.text))
        print("  titre:", (re.search(r"<title>(.*?)</title>", r.text, re.S) or [None, ""])[1].strip()[:150])
        print("  liens direct:", json.dumps(liens, ensure_ascii=False)[:1500])
    except Exception as e:
        print("=====", url, "ERREUR", e)
