"""Émissions telles qu'affichées (page, email, terminal) : invités annoncés ajoutés,
puis doublons fusionnés. La base n'est jamais modifiée par ces deux étapes."""

from __future__ import annotations

from datetime import datetime

from grille import annonces, db, fusion


def emissions(connexion, depuis: datetime, jusqua: datetime, plateformes: list[str] | None = None) -> list[dict]:
    liste = db.lister(connexion, depuis, jusqua)
    if plateformes is not None:
        liste = [e for e in liste if e["plateforme"] in plateformes]
    return fusion.fusionner(annonces.enrichir(liste, db.annonces(connexion)))
