"""Émissions telles qu'affichées (page, email, terminal) : invités annoncés ajoutés,
passages médias des agendas rattachés à leur émission, puis doublons fusionnés.
La base n'est jamais modifiée par ces étapes."""

from __future__ import annotations

from datetime import datetime

from grille import agendas, annonces, db, fusion


def emissions(connexion, depuis: datetime, jusqua: datetime, plateformes: list[str] | None = None) -> list[dict]:
    liste = db.lister(connexion, depuis, jusqua)
    if plateformes is not None:
        liste = [e for e in liste if e["plateforme"] in plateformes]
    return fusion.fusionner(agendas.rattacher(annonces.enrichir(liste, db.annonces(connexion))))
