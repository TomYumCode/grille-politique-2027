"""TEMPORAIRE : réponses brutes (requête du collecteur) pour le test du créneau vide."""
import json, os
from datetime import date, datetime, timedelta
import requests
from grille import radio
from grille.tv import PARIS

cle = os.environ["RADIOFRANCE_API_KEY"]
for jour in (date(2026, 10, 12), date(2026, 10, 19)):
    d = datetime.combine(jour, datetime.min.time(), PARIS) + timedelta(hours=18)
    f = d + timedelta(hours=1, minutes=30)
    print("=====", jour)
    print(json.dumps(radio.lire_grille(requests.Session(), cle, radio.requete("FRANCECULTURE", d, f)),
                     ensure_ascii=False))
