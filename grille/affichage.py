"""Émissions telles qu'affichées (page, email, terminal) : invités annoncés ajoutés,
passages médias des agendas rattachés à leur émission, puis doublons fusionnés ; une personne
annoncée présente n'est plus comptée parmi les personnes seulement citées.
La base n'est jamais modifiée par ces étapes."""

from __future__ import annotations

from datetime import datetime

from grille import agendas, annonces, db, fusion


def emissions(connexion, depuis: datetime, jusqua: datetime, plateformes: list[str] | None = None) -> list[dict]:
    liste = db.lister(connexion, depuis, jusqua)
    if plateformes is not None:
        liste = [e for e in liste if e["plateforme"] in plateformes]
    liste = agendas.rattacher(annonces.enrichir(liste, db.annonces(connexion)))
    return [dict(e, cites=[n for n in e.get("cites") or [] if n not in e["invites"]]) for e in fusion.fusionner(liste)]
