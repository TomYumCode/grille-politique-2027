"""Bouton « Présidentielle 2027 » de la page : émissions consacrées à la campagne,
parmi toutes les émissions politiques retenues (« Toute la politique »).

Une émission est de la campagne si :
- un candidat, ou un membre d'équipe de campagne (« campagne: true » dans politique.yaml),
  y est présent (invité, interviewé, en meeting) ;
- un candidat est nommé dans le titre, même s'il n'y est que cité (« Glucksmann : gros scandale
  électoral ? ») ; cité seulement dans le résumé, il ne suffit pas ;
- c'est un meeting ;
- elle vient de la chaîne d'un parti ou d'un candidat ;
- son titre ou son résumé contient un mot de la rubrique « presidentielle: » de politique.yaml
  (« présidentielle », « candidat », « primaire », « sondage »…).

Calculé à l'affichage, à chaque collecte : quand l'invité d'une émission est annoncé (guide,
agenda d'un parti, communiqué), elle entre dans la campagne sans autre réglage.
"""

from __future__ import annotations

from grille.config import Configuration
from grille.filtre import _contient, normaliser

CATEGORIES_DE_CAMPAGNE = ("parti", "personnalite politique")


class Campagne:
    def __init__(self, config: Configuration):
        self._candidats = {p["nom"] for p in config.candidats}
        self._personnes = self._candidats | {
            p["nom"] for p in config.personnalites if p.get("campagne")}
        self._formes = {p["nom"]: [normaliser(p["nom"])] + [normaliser(a) for a in p.get("alias") or []]
                        for p in config.candidats}
        self._mots = [(m, normaliser(m)) for m in config.mots_presidentielle]
        self._chaines = {c.nom for c in config.chaines
                         if normaliser(c.categorie).startswith(CATEGORIES_DE_CAMPAGNE)}

    def motif(self, e: dict) -> str:
        """Pourquoi l'émission est de la campagne ; texte vide si elle ne l'est pas."""
        presents = [n for n in e["invites"] if n in self._personnes]
        if presents:
            return f"présent : {presents[0]}"
        titre_n = normaliser(e["titre"])
        dans_le_titre = [n for n in e.get("cites") or [] if n in self._candidats
                         and any(_contient(titre_n, f) for f in self._formes[n])]
        if dans_le_titre:
            return f"candidat dans le titre : {dans_le_titre[0]}"
        if e["categorie"] == "meeting":
            return "meeting"
        chaines = [s["chaine"] for s in e.get("sources") or [e]]
        if any(c in self._chaines for c in chaines):
            return "chaîne de parti ou de candidat"
        texte = normaliser(f"{e['titre']}\n{e.get('resume') or ''}")
        for mot, mot_n in self._mots:
            if _contient(texte, mot_n):
                return f"« {mot} »"
        return ""
