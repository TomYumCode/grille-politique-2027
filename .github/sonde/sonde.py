"""TEMPORAIRE : réponses brutes (requête du collecteur) pour le test des parties incluses."""
import json, os
from datetime import datetime
import requests
from grille import radio
from grille.tv import PARIS

cle = os.environ["RADIOFRANCE_API_KEY"]
for station, d, f in (("FRANCECULTURE", datetime(2026, 10, 25, 10, 55, tzinfo=PARIS), datetime(2026, 10, 25, 12, 5, tzinfo=PARIS)),):
    print("=====", station)
    print(json.dumps(radio.lire_grille(requests.Session(), cle, radio.requete(station, d, f)), ensure_ascii=False))
