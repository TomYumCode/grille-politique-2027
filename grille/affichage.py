"""Émissions telles qu'affichées (page, email, terminal) : invités annoncés ajoutés,
passages médias des agendas rattachés à leur émission, puis doublons fusionnés ; une personne
annoncée présente n'est plus comptée parmi les personnes seulement citées.
La base n'est jamais modifiée par ces étapes."""

from __future__ import annotations

import re
from datetime import datetime

from grille import agendas, annonces, db, fusion
from grille.filtre import CRENEAU_INVITE, normaliser

LONGUEUR_PRESENTATION = 180


def emissions(connexion, depuis: datetime, jusqua: datetime, plateformes: list[str] | None = None) -> list[dict]:
    liste = db.lister(connexion, depuis, jusqua)
    if plateformes is not None:
        liste = [e for e in liste if e["plateforme"] in plateformes]
    liste = agendas.rattacher(annonces.enrichir(liste, db.annonces(connexion)))
    return [dict(e, cites=[n for n in e.get("cites") or [] if n not in e["invites"]]) for e in fusion.fusionner(liste)]


def presentation(e: dict) -> str:
    """Phrase de la radio qui présente l'invité d'une émission à invités, quand l'outil ne le
    connaît pas : « Dominique Schelcher, patron de Coopérative U, est l'invité de Céline
    Landreau » (RTL). Vide pour la télévision, dont les résumés décrivent surtout l'émission
    (« Installés dans le loft de C à vous… ») ; son sous-titre, déjà dans le titre, nomme l'invité."""
    if e["plateforme"] != "radio" or e["invites"] or not (e.get("resume") or "").strip():
        return ""
    if not CRENEAU_INVITE.search(normaliser(e["titre"])):
        return ""
    phrase = re.split(r"(?<=[.!?])\s", e["resume"].strip())[0]
    if len(phrase) > LONGUEUR_PRESENTATION:
        phrase = phrase[:LONGUEUR_PRESENTATION - 1].rsplit(" ", 1)[0] + "…"
    return phrase
