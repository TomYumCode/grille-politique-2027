"""TEMPORAIRE : que renvoie l'API Radio France pour France Culture autour de 18 h ?"""
import json, os
from datetime import date, datetime, timedelta
import requests
from grille.acces import RADIOFRANCE_API
from grille.tv import PARIS

cle = os.environ["RADIOFRANCE_API_KEY"]
Q = """{{ grid(start: {d}, end: {f}, station: FRANCECULTURE) {{
  __typename
  ... on DiffusionStep {{ id start end diffusion {{ id title standFirst url show {{ title }} }} }}
  ... on BlankStep {{ id title start end }}
  ... on TrackStep {{ id start end }}
}} }}"""
for jour in (date(2026, 10, 13), date(2026, 10, 14), date(2026, 10, 15), date(2026, 10, 16), date(2026, 10, 19)):
    d = datetime.combine(jour, datetime.min.time(), PARIS) + timedelta(hours=17)
    f = d + timedelta(hours=3)
    r = requests.post(RADIOFRANCE_API, params={"x-token": cle},
                      json={"query": Q.format(d=int(d.timestamp()), f=int(f.timestamp()))}, timeout=30)
    print(f"===== {jour} HTTP {r.status_code}")
    corps = r.json()
    if corps.get("errors"):
        print("ERREURS", json.dumps(corps["errors"], ensure_ascii=False)[:800])
    for e in (corps.get("data") or {}).get("grid") or []:
        h = datetime.fromtimestamp(int(e["start"]), PARIS).strftime("%H:%M") if e.get("start") else "?"
        print(h, json.dumps(e, ensure_ascii=False)[:600])
