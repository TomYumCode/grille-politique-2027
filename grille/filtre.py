"""Filtre politique : liste blanche, puis mots-clés (le classement par modèle viendra au lot 6).

Les émissions écartées qui pourraient tout de même être politiques sont notées comme
« cas douteux » (`noter_douteux`) : ce sont elles que le modèle aurait à juger.

La comparaison ignore majuscules, accents et ponctuation, et se fait mot à mot :
« Attal » trouve « Gabriel Attal, invité » mais pas « Attalens ».

Personnes nommées : « présentes » (invitées, interviewées, en meeting) ou seulement
« citées » (sujet d'un commentaire d'actualité : « Glucksmann : la surprise ? »).
Voir `FiltrePolitique.presences`.
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


# Mots qui, juste avant un nom, disent que la personne est là (« avec Gabriel Attal »,
# « invitée : Marine Tondelier », « meeting de Jean-Luc Mélenchon »)…
_SIGNES_AVANT = ["avec", "invite", "invitee", "invites", "invitees", "recoit", "en presence de", "face a",
                 "entretien avec", "interview de", "interview d", "interroge", "interrogee", "accueille"]
# … ou d'un évènement où elle parle (ne compte pas dans un commentaire : « réaction au meeting de … »).
_SIGNES_EVENEMENT = ["meeting de", "meeting d", "discours de", "discours d", "allocution de", "allocution d",
                     "reunion publique de", "reunion publique d", "conference de presse de", "conference de presse d",
                     "declaration de", "declaration d", "voeux de", "voeux d"]
# Mots qui, juste après un nom, disent la même chose (« Gabriel Attal, invité de… », « … répond »).
_SIGNES_APRES = ["invite", "invitee", "sera l invite", "sera l invitee", "est l invite", "est l invitee",
                 "repond", "s exprime", "en meeting", "en direct", "face a", "sur le plateau", "en duplex",
                 "en plateau"]
# Titres de commentaire d'actualité : les noms qu'ils contiennent sont des sujets.
_COMMENTAIRE = ["reaction", "reactions", "reagit", "reagir", "reagissons", "debrief", "debriefing", "decryptage",
                "decrypte", "decryptons", "analyse", "analysons", "revue de presse", "retour sur", "commente",
                "commentons", "parodie", "cafe rhetorique"]
# Émission à invités, d'après son titre (« L'Invité de 7h50 », « Le grand entretien »).
CRENEAU_INVITE = re.compile(r"\b(invit\w*|interview\w*|entretien\w*|grand jury|face a face)\b")
# Rediffusion d'un meeting que le guide titre « L'interview — … ».
_REDIFFUSION = ["retransmission", "rediffusion", "extraits", "en differe"]
_EVENEMENTS = ["meeting", "discours", "reunion publique"]
FENETRE_AVANT, FENETRE_APRES = 6, 4  # mots examinés autour du nom
# Homonymes : un nom de famille seul (« Bompard ») précédé d'un autre prénom (« Alexandre
# Bompard », PDG de Carrefour) n'est pas la personne suivie (Manuel Bompard). Ces mots à
# majuscule devant un nom ne sont pas des prénoms.
_PAS_PRENOMS = {
    "le", "la", "les", "l", "un", "une", "de", "du", "des", "d", "et", "ou", "mais", "pour", "avec", "selon", "face",
    "chez", "contre", "par", "sur", "sans", "sous", "vers", "entre", "avant", "apres", "quand", "pourquoi", "comment",
    "qui", "que", "si", "ce", "cette", "monsieur", "madame", "mademoiselle", "m", "mme", "mr", "president",
    "presidente", "ministre", "depute", "deputee", "senateur", "senatrice", "maire", "candidat", "candidate",
    "invite", "invitee", "interview", "debat", "meeting", "discours", "affaire", "equipe", "clan", "effet", "camp",
    "famille", "generation", "france", "gouvernement", "premier", "premiere", "secretaire", "porte", "chef", "leader",
}
_MOT_MAJUSCULE = re.compile(r"(?<![\w'’-])([A-ZÀ-Ý][a-zà-ÿ]+(?:-[A-ZÀ-Ý][a-zà-ÿ]+)?)\s+$")
# « avec » sert à tout (« vainqueur avec près de 66 % des voix, Raphaël Glucksmann… ») :
# il ne compte que dans le même membre de phrase que le nom (pas de virgule ni de point entre).
_COUPURE = "0coupure0"


def normaliser(texte: str) -> str:
    """Minuscules, sans accents ni ponctuation, mots séparés par une espace."""
    sans_accents = unicodedata.normalize("NFKD", texte or "")
    sans_accents = "".join(c for c in sans_accents if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^0-9a-z]+", " ", sans_accents.lower()).split())


def _contient(texte_normalise: str, terme_normalise: str) -> bool:
    return bool(terme_normalise) and f" {terme_normalise} " in f" {texte_normalise} "


def _fenetre_contient(mots: list[str], signes: list[str]) -> bool:
    return any(_contient(" ".join(mots), s) for s in signes)


def _commence_par(texte_normalise: str, debut_normalise: str) -> bool:
    """« franc jeu gabriel attal » commence par « franc jeu », mais « franchise » non."""
    return bool(debut_normalise) and f"{texte_normalise} ".startswith(f"{debut_normalise} ")


@dataclass
class Decision:
    filtre: str  # LISTE_BLANCHE ou MOTS_CLES
    categorie: str
    invites: list[str] = field(default_factory=list)  # personnes présentes
    motif: str = ""  # ce qui a déclenché le filtre, pour comprendre un faux positif
    cites: list[str] = field(default_factory=list)  # personnes seulement citées


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
        self._fonctions = [(m, normaliser(m)) for m in config.fonctions_politiques]
        # Noms de famille employés seuls (alias d'un mot, fin du nom complet), avec le prénom attendu.
        self._noms_seuls = []
        for p in config.candidats + config.personnalites:
            for a in p.get("alias") or []:
                if " " not in a.strip() and normaliser(p["nom"]).endswith(" " + normaliser(a)):
                    prenom = normaliser(p["nom"])[: -len(normaliser(a))].strip()
                    self._noms_seuls.append((re.compile(rf"(?<![\w-]){re.escape(a)}(?![\w-])", re.IGNORECASE), prenom))
        self.douteux: list[dict] = []  # cas douteux vus pendant la collecte en cours

    def sans_homonymes(self, texte: str) -> str:
        """Texte où « Alexandre Bompard » ne peut plus passer pour Manuel Bompard (nom de famille
        seul précédé d'un autre prénom) ; « Manuel Bompard », « Bompard » seul ou « M. Bompard » restent."""
        if not texte:
            return texte
        for motif, prenom in self._noms_seuls:
            def remplacer(m, prenom=prenom):
                avant = _MOT_MAJUSCULE.search(texte[: m.start()])
                if avant and normaliser(avant.group(1)) not in _PAS_PRENOMS and normaliser(avant.group(1)) != prenom \
                        and not prenom.endswith(normaliser(avant.group(1))):
                    return "(homonyme)"
                return m.group(0)
            texte = motif.sub(remplacer, texte)
        return texte

    def invites(self, texte: str) -> list[str]:
        t = normaliser(texte)
        return [nom for nom, formes in self._personnes if any(_contient(t, f) for f in formes)]

    @staticmethod
    def categorie(titre: str, description: str) -> str:
        if any(_contient(normaliser(titre), m) for m in _COMMENTAIRE):
            return "analyse"  # « Réaction au meeting de … » n'est pas un meeting
        trouvee = "analyse"
        for texte in (normaliser(titre), normaliser(description)):
            for categorie, indices in _INDICES_CATEGORIE:
                if any(_contient(texte, i) for i in indices):
                    trouvee = categorie
                    break
            else:
                continue
            break
        # « L'interview — Jean-Luc Mélenchon », décrite comme la rediffusion de son meeting.
        description_n = normaliser(description)
        if (trouvee in ("interview", "analyse") and any(_contient(description_n, m) for m in _REDIFFUSION)
                and any(_contient(description_n, m) for m in _EVENEMENTS)):
            return "meeting"
        return trouvee

    def presences(self, chaine: Chaine, titre: str, description: str, emission_blanche: bool = False
                  ) -> tuple[list[str], list[str]]:
        """Sépare les personnes nommées en (présentes, citées).

        Présente : sa propre chaîne ; un signe autour du nom (« avec », « invité », « répond »,
        « meeting de »…) ; ou une émission d'interview, de débat ou de meeting (d'après le
        titre, ou de la liste blanche) qui la nomme dans son titre, sauf un débat titré par une
        question ; ou, dans une émission
        d'interview sans nom dans le titre, la première personne du résumé (« L'invité de la
        matinale » : « Anne Goscinny, co-auteure… »). Les autres sont seulement citées.
        """
        titre_n, description_n, chaine_n = normaliser(titre), normaliser(description), normaliser(chaine.nom)
        commentaire = any(_contient(titre_n, m) for m in _COMMENTAIRE)
        signes_avant = _SIGNES_AVANT + ([] if commentaire else _SIGNES_EVENEMENT)
        signes_sans_avec = [s for s in signes_avant if s != "avec"]
        categorie_titre = self.categorie(titre, "")
        emission_a_invite = not commentaire and (emission_blanche or categorie_titre != "analyse")
        # Débat dont le titre pose une question sur quelqu'un (« Glucksmann candidat de la gauche :
        # la social-démocratie fait-elle rêver ? ») : c'est le sujet, les débatteurs sont d'autres.
        if categorie_titre == "débat" and "?" in titre:
            emission_a_invite = False

        def position(texte_n: str, formes: list[str]) -> int | None:
            places = [f" {texte_n} ".find(f" {f} ") for f in formes if _contient(texte_n, f)]
            return min(places) if places else None

        def signe_autour(texte: str, formes: list[str]) -> bool:
            mots = normaliser(texte).split()
            for f in formes:
                taille = len(f.split())
                for i in range(len(mots) - taille + 1):
                    if mots[i:i + taille] == f.split() and (
                            _fenetre_contient(mots[max(0, i - FENETRE_AVANT):i], signes_sans_avec)
                            or _fenetre_contient(mots[i + taille:i + taille + FENETRE_APRES], _SIGNES_APRES)):
                        return True
            mots = normaliser(re.sub(r"[,.;!?]", f" {_COUPURE} ", texte or "")).split()
            for f in formes:
                taille = len(f.split())
                for i in range(len(mots) - taille + 1):
                    avant = mots[max(0, i - FENETRE_AVANT):i]
                    if _COUPURE in avant:
                        avant = avant[len(avant) - avant[::-1].index(_COUPURE):]
                    if mots[i:i + taille] == f.split() and "avec" in avant:
                        return True
            return False

        presents, cites = [], []
        # Chaîne d'une personnalité (« Jean-Luc Mélenchon ») : elle est dans ses vidéos, nommée ou non.
        proprietaire = [nom for nom, formes in self._personnes if any(f == chaine_n for f in formes)]
        nommes = [(nom, formes) for nom, formes in self._personnes
                  if nom in proprietaire or any(_contient(titre_n, f) or _contient(description_n, f) for f in formes)]
        # Émission d'interview sans nom dans le titre : la première personne du résumé est l'invitée.
        premiere = None
        if categorie_titre == "interview" and not commentaire and not any(
                position(titre_n, formes) is not None for _, formes in nommes):
            dans_resume = [(position(description_n, formes), nom) for nom, formes in nommes]
            dans_resume = [x for x in dans_resume if x[0] is not None]
            premiere = min(dans_resume)[1] if dans_resume else None
        for nom, formes in nommes:
            present = (
                nom in proprietaire
                or signe_autour(titre, formes) or signe_autour(description, formes)
                or (emission_a_invite and position(titre_n, formes) is not None)
                or nom == premiere
            )
            (presents if present else cites).append(nom)
        return presents, cites

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

    def decider(self, chaine: Chaine, titre: str, description: str = "", sous_titre: str = "") -> Decision | None:
        """Renvoie la décision si l'émission est politique, None sinon. Le sous-titre d'un
        guide TV (« L'interview » — « Jean-Luc Mélenchon ») compte avec la description pour
        les mots-clés, et avec le titre pour repérer qui est présent."""
        titre, sous_titre, description = self.sans_homonymes(titre), self.sans_homonymes(sous_titre), \
            self.sans_homonymes(description)
        titre_complet = f"{titre} — {sous_titre}" if sous_titre else titre
        if sous_titre:
            description = f"{sous_titre}\n{description}"
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
        def decision(filtre: str, motif: str) -> Decision:
            presents, cites = self.presences(chaine, titre_complet, description, motif.startswith("émission"))
            return Decision(filtre, self.categorie(titre_complet, description), presents, motif, cites)

        if motif:
            return decision(LISTE_BLANCHE, motif)
        texte_n = normaliser(texte)
        for mot, mot_n in self._mots:
            if _contient(texte_n, mot_n):
                return decision(MOTS_CLES, f"« {mot} »")
        for mot, mot_n in self._mots_titre:
            if _contient(titre_n, mot_n):
                return decision(MOTS_CLES, f"« {mot} » dans le titre")
        # Émission à invités dont l'invité a une fonction politique, même absent des listes
        # (« L'Invité de 7h50 — Edouard Geffray, ministre de l'Education nationale »).
        titre_complet_n = normaliser(titre_complet)
        if CRENEAU_INVITE.search(titre_complet_n) or any(
                _commence_par(titre_complet_n, e) for _, e in self._emissions_a_invites):
            for mot, mot_n in self._fonctions:
                if _contient(texte_n, mot_n) or _contient(titre_complet_n, mot_n):
                    return decision(MOTS_CLES, f"invité « {mot} »")
        return None
