"""TEMPORAIRE : schéma de l'API Radio France (étapes de grille) et créneau vide du 19 octobre."""
import json, os
from datetime import date, datetime, timedelta
import requests
from grille.acces import RADIOFRANCE_API
from grille.tv import PARIS

cle = os.environ["RADIOFRANCE_API_KEY"]


def envoyer(q):
    r = requests.post(RADIOFRANCE_API, params={"x-token": cle}, json={"query": q}, timeout=30)
    return r.status_code, r.json()


for nom in ("DiffusionStep", "BlankStep", "TrackStep", "Step", "GridStep", "Diffusion", "Show", "Query"):
    code, corps = envoyer('{ __type(name: "%s") { name kind fields { name type { name kind ofType { name } } } '
                          'possibleTypes { name } } }' % nom)
    print("=====", nom, code, json.dumps(corps, ensure_ascii=False)[:2500])

d = datetime.combine(date(2026, 10, 19), datetime.min.time(), PARIS) + timedelta(hours=18)
f = d + timedelta(hours=1, minutes=30)
for champs in ("id start end children { id start end ... on DiffusionStep { diffusion { title show { title } } } }",
               "id start end show { title }", "id start end diffusionId", "id start end title"):
    q = "{ grid(start: %d, end: %d, station: FRANCECULTURE) { ... on DiffusionStep { %s } } }" % (
        int(d.timestamp()), int(f.timestamp()), champs)
    code, corps = envoyer(q)
    print("----- essai", champs[:40], code, json.dumps(corps, ensure_ascii=False)[:1200])
