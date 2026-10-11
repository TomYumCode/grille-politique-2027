"""Filtre politique : liste blanche, puis mots-clés (le classement par modèle viendra au lot 6).

Les émissions écartées qui pourraient tout de même être politiques sont notées comme
« cas douteux » (`noter_douteux`) : ce sont elles que le modèle aurait à juger.

La comparaison ignore majuscules, accents et ponctuation, et se fait mot à mot :
« Attal » trouve « Gabriel Attal, invité » mais pas « Attalens ».
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from grille.config import Chaine, Configuration

LISTE_BLANCHE = "liste blanche"
MOTS_CLES = "mots-clés"

# Indices de catégorie, cherchés dans le titre puis la description (formes normalisées).
_INDICES_CATEGORIE = [
    ("débat", ["debat", "debats", "face a face", "duel", "entre deux tours"]),
    ("meeting", ["meeting", "discours", "declaration", "conference de presse", "allocution", "voeux",
                 "reunion publique"]),
    ("interview", ["interview", "entretien", "invite", "invitee", "l invite", "grand jury", "questions politiques",
                   "les quatre verites", "face aux francais", "l heure de verite", "grand entretien"]),
]


def normaliser(texte: str) -> str:
    """Minuscules, sans accents ni ponctuation, mots séparés par une espace."""
    sans_accents = unicodedata.normalize("NFKD", texte or "")
    sans_accents = "".join(c for c in sans_accents if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^0-9a-z]+", " ", sans_accents.lower()).split())


def _contient(texte_normalise: str, terme_normalise: str) -> bool:
    return bool(terme_normalise) and f" {terme_normalise} " in f" {texte_normalise} "


def _commence_par(texte_normalise: str, debut_normalise: str) -> bool:
    """« franc jeu gabriel attal » commence par « franc jeu », mais « franchise » non."""
    return bool(debut_normalise) and f"{texte_normalise} ".startswith(f"{debut_normalise} ")


@dataclass
class Decision:
    filtre: str  # LISTE_BLANCHE ou MOTS_CLES
    categorie: str
    invites: list[str] = field(default_factory=list)
    motif: str = ""  # ce qui a déclenché le filtre, pour comprendre un faux positif


class FiltrePolitique:
    def __init__(self, config: Configuration):
        lb = config.liste_blanche
        self._chaines_blanches = {normaliser(n) for n in lb.get("chaines") or []}
        self._categories_blanches = [normaliser(c) for c in lb.get("categories_de_chaine") or []]
        # (titre normalisé, chaîne normalisée ou "" pour toutes les chaînes)
        self._emissions_blanches = [
            (normaliser(e), "") if isinstance(e, str) else (normaliser(e["titre"]), normaliser(e.get("chaine", "")))
            for e in lb.get("emissions") or []
        ]
        self._mots = [(m, normaliser(m)) for m in config.mots_cles + config.noms_a_reperer()]
        self._mots_titre = [(m, normaliser(m)) for m in config.mots_cles_titre]
        # Personnes repérables comme invités : forme affichée + toutes ses formes normalisées.
        self._personnes = [
            (p["nom"], [normaliser(p["nom"])] + [normaliser(a) for a in p.get("alias") or []])
            for p in config.candidats + config.personnalites
        ]
        douteux = config.cas_douteux
        partis_ambigus = [n for p in config.partis if p.get("ambigu") for n in [p["nom"]] + (p.get("alias") or [])]
        self._mots_douteux = [(m, normaliser(m)) for m in (douteux.get("mots") or []) + partis_ambigus]
        self._emissions_a_invites = [(e, normaliser(e)) for e in douteux.get("emissions_a_invites") or []]
        self.douteux: list[dict] = []  # cas douteux vus pendant la collecte en cours

    def invites(self, texte: str) -> list[str]:
        t = normaliser(texte)
        return [nom for nom, formes in self._personnes if any(_contient(t, f) for f in formes)]

    @staticmethod
    def categorie(titre: str, description: str) -> str:
        for texte in (normaliser(titre), normaliser(description)):
            for categorie, indices in _INDICES_CATEGORIE:
                if any(_contient(texte, i) for i in indices):
                    return categorie
        return "analyse"

    def motif_douteux(self, titre: str, description: str = "") -> str | None:
        """Pourquoi une émission écartée pourrait quand même être politique (None : rien de tel)."""
        titre_n = normaliser(titre)
        for emission, emission_n in self._emissions_a_invites:
            if _commence_par(titre_n, emission_n):
                return f"émission à invités « {emission} »"
        texte_n = normaliser(f"{titre}\n{description}")
        for mot, mot_n in self._mots_douteux:
            if _contient(texte_n, mot_n):
                return f"« {mot} »"
        return None

    def noter_douteux(self, id_: str, source: str, chaine: Chaine, titre: str, description: str, debut) -> None:
        """À appeler pour une émission écartée : la garde si elle est douteuse."""
        motif = self.motif_douteux(titre, description)
        if motif:
            self.douteux.append({"id": id_, "source": source, "chaine": chaine.nom, "titre": titre,
                                 "description": " ".join((description or "").split())[:500],
                                 "debut": debut.isoformat(timespec="seconds"), "motif": motif})

    def decider(self, chaine: Chaine, titre: str, description: str = "") -> Decision | None:
        """Renvoie la décision si l'émission est politique, None sinon."""
        texte = f"{titre}\n{description}"
        titre_n = normaliser(titre)
        motif = ""
        if normaliser(chaine.nom) in self._chaines_blanches:
            motif = f"chaîne « {chaine.nom} »"
        elif any(normaliser(chaine.categorie).startswith(c) for c in self._categories_blanches if c):
            motif = f"catégorie de chaîne « {chaine.categorie} »"
        elif any(
            _commence_par(titre_n, t) and (not c or c == normaliser(chaine.nom)) for t, c in self._emissions_blanches
        ):
            motif = f"émission « {titre} »"
        if motif:
            return Decision(LISTE_BLANCHE, self.categorie(titre, description), self.invites(texte), motif)

        texte_n = normaliser(texte)
        for mot, mot_n in self._mots:
            if _contient(texte_n, mot_n):
                return Decision(MOTS_CLES, self.categorie(titre, description), self.invites(texte), f"« {mot} »")
        for mot, mot_n in self._mots_titre:
            if _contient(titre_n, mot_n):
                return Decision(
                    MOTS_CLES, self.categorie(titre, description), self.invites(texte), f"« {mot} » dans le titre"
                )
        return None
