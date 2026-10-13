"""Lecture et contrôle des fichiers de configuration (config/*.yaml).

Une erreur de syntaxe YAML ou un fichier absent est bloquant (ErreurConfig).
Une ligne de chaîne invalide ne l'est pas : elle est écartée et rangée dans
`Configuration.anomalies`, pour être signalée sans arrêter les autres sources.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DOSSIER_CONFIG = Path(__file__).resolve().parent.parent / "config"
PLATEFORMES = ("tv", "radio", "youtube", "twitch", "web")

_YOUTUBE = re.compile(
    r"^https?://(?:www\.)?youtube\.com/"
    r"(?:@(?P<handle>[\w.\-]+)|channel/(?P<channel_id>UC[\w-]{22})|user/(?P<user>[\w.\-]+)|c/(?P<custom>[\w.\-]+))/?$"
)
_TWITCH = re.compile(r"^https?://(?:www\.)?twitch\.tv/(?P<login>[A-Za-z0-9_]{3,25})/?$")
_XMLTV_ID = re.compile(r"^[\w.\-]+$")
_STATION = re.compile(r"^[A-Z][A-Z0-9_]+$")  # code de station Radio France, ex. FRANCEINTER
_WEB = re.compile(r"^https?://\S+$")


class ErreurConfig(Exception):
    """Configuration illisible : rien ne peut tourner."""


@dataclass(frozen=True)
class Chaine:
    plateforme: str
    nom: str
    adresse: str
    categorie: str
    a_confirmer: bool = False
    # Adresses pour regarder le direct (facultatives, utiles surtout pour la télévision).
    direct: tuple[str, ...] = ()
    # Logo imposé dans chaines.yaml (sinon celui fourni par la source).
    logo: str = ""
    # Identifiant extrait de l'adresse : handle ou ID YouTube, login Twitch, ID XMLTV, station…
    cle: dict = field(default_factory=dict, hash=False, compare=False)


@dataclass
class Configuration:
    chaines: list[Chaine]
    candidats: list[dict]
    personnalites: list[dict]
    partis: list[dict]
    liste_blanche: dict
    mots_cles: list[str]
    mots_cles_titre: list[str] = field(default_factory=list)
    tv_heures_masquees: tuple[int, int] | None = None  # (de, a) : début dans [de, a[ → ignoré
    # Cas douteux à mesurer : {"mots": [...], "emissions_a_invites": [...]}.
    cas_douteux: dict = field(default_factory=dict)
    # Fonctions qui font retenir une émission à invités (« ministre », « député »…).
    fonctions_politiques: list[str] = field(default_factory=list)
    # Mots qui classent une émission dans « Présidentielle 2027 » (grille/campagne.py).
    mots_presidentielle: list[str] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)

    def nommer(self, noms: list[str]) -> list[str]:
        """« Jean-Philippe Tanguy (RN) » : sigle de politique.yaml après le nom, s'il est connu."""
        sigles = {p["nom"]: p["sigle"] for p in self.candidats + self.personnalites if p.get("sigle")}
        return [f"{n} ({sigles[n]})" if n in sigles else n for n in noms]

    def noms_a_reperer(self) -> list[str]:
        """Noms et alias de candidats, personnalités et partis non ambigus."""
        noms = []
        for entree in self.candidats + self.personnalites + self.partis:
            if entree.get("ambigu"):
                continue
            noms.append(entree["nom"])
            noms.extend(entree.get("alias") or [])
        return noms


def _lire_yaml(chemin: Path) -> dict:
    try:
        with chemin.open(encoding="utf-8") as f:
            contenu = yaml.safe_load(f)
    except FileNotFoundError as e:
        raise ErreurConfig(f"{chemin} : fichier introuvable") from e
    except yaml.YAMLError as e:
        raise ErreurConfig(f"{chemin} : YAML invalide\n{e}") from e
    if not isinstance(contenu, dict):
        raise ErreurConfig(f"{chemin} : le fichier doit contenir des rubriques (clé: valeur)")
    return contenu


def analyser_adresse(plateforme: str, adresse: str) -> dict | None:
    """Renvoie l'identifiant tiré de l'adresse, ou None si elle n'a pas la forme attendue."""
    if plateforme == "youtube":
        m = _YOUTUBE.match(adresse)
        return {k: v for k, v in m.groupdict().items() if v} if m else None
    if plateforme == "twitch":
        m = _TWITCH.match(adresse)
        return {"login": m["login"].lower()} if m else None
    if plateforme == "tv":
        return {"xmltv_id": adresse} if _XMLTV_ID.match(adresse) else None
    if plateforme == "radio":
        # Code de station Radio France (API), ou adresse de la grille d'une radio privée.
        if _STATION.match(adresse):
            return {"station": adresse}
        return {"url": adresse} if _WEB.match(adresse) else None
    if plateforme == "web":
        return {"url": adresse} if _WEB.match(adresse) else None
    return None


def _lire_chaines(brut: object, anomalies: list[str]) -> list[Chaine]:
    if not isinstance(brut, list):
        raise ErreurConfig("chaines.yaml : la rubrique « chaines: » doit être une liste")
    chaines, vues = [], set()
    for i, ligne in enumerate(brut, start=1):
        if not isinstance(ligne, dict):
            anomalies.append(f"chaines.yaml, chaîne n° {i} : ligne illisible ({ligne!r})")
            continue
        nom = str(ligne.get("nom") or "").strip()
        etiquette = f"chaines.yaml, chaîne n° {i} ({nom or 'sans nom'})"
        manquants = [c for c in ("plateforme", "nom", "adresse", "categorie") if not ligne.get(c)]
        if manquants:
            anomalies.append(f"{etiquette} : champ manquant {', '.join(manquants)}")
            continue
        plateforme = str(ligne["plateforme"]).strip().lower()
        adresse = str(ligne["adresse"]).strip()
        if plateforme not in PLATEFORMES:
            anomalies.append(f"{etiquette} : plateforme « {plateforme} » inconnue ({', '.join(PLATEFORMES)})")
            continue
        cle = analyser_adresse(plateforme, adresse)
        if cle is None:
            anomalies.append(f"{etiquette} : adresse {plateforme} invalide « {adresse} »")
            continue
        if (plateforme, adresse.lower()) in vues:
            anomalies.append(f"{etiquette} : doublon de « {adresse} », ignoré")
            continue
        # « direct » : une adresse, ou une liste quand la chaîne partage son canal (LCP / Public Sénat).
        brut = ligne.get("direct") or []
        direct = []
        for d in [brut] if isinstance(brut, str) else brut:
            d = str(d).strip()
            if _WEB.match(d):
                direct.append(d)
            else:
                anomalies.append(f"{etiquette} : adresse de direct invalide « {d} », ignorée")
        direct = tuple(direct)
        logo = str(ligne.get("logo") or "").strip()
        if logo and not _WEB.match(logo):
            anomalies.append(f"{etiquette} : adresse de logo invalide « {logo} », ignorée")
            logo = ""
        vues.add((plateforme, adresse.lower()))
        chaines.append(
            Chaine(
                plateforme, nom, adresse, str(ligne["categorie"]).strip(), bool(ligne.get("a_confirmer")), direct,
                logo, cle
            )
        )
    return chaines


def _liste_de_noms(contenu: dict, rubrique: str, fichier: str) -> list[dict]:
    entrees = contenu.get(rubrique) or []
    if not isinstance(entrees, list) or not all(isinstance(e, dict) and e.get("nom") for e in entrees):
        raise ErreurConfig(f"{fichier} : chaque entrée de « {rubrique}: » doit avoir un « nom »")
    return entrees


def charger(dossier: Path = DOSSIER_CONFIG) -> Configuration:
    anomalies: list[str] = []
    chaines = _lire_chaines(_lire_yaml(dossier / "chaines.yaml").get("chaines"), anomalies)

    politique = _lire_yaml(dossier / "politique.yaml")
    candidats = _liste_de_noms(politique, "candidats", "politique.yaml")
    if not candidats:
        raise ErreurConfig("politique.yaml : la liste « candidats: » est vide")
    mots_cles = politique.get("mots_cles") or []
    mots_cles_titre = politique.get("mots_cles_titre") or []
    for rubrique, liste in (("mots_cles", mots_cles), ("mots_cles_titre", mots_cles_titre)):
        if not isinstance(liste, list) or not all(isinstance(m, str) for m in liste):
            raise ErreurConfig(f"politique.yaml : « {rubrique}: » doit être une liste de textes")
    masque = politique.get("tv_heures_masquees")
    if masque is not None:
        try:
            masque = (int(masque["de"]), int(masque["a"]))
        except (TypeError, KeyError, ValueError) as e:
            raise ErreurConfig("politique.yaml : « tv_heures_masquees: » doit s'écrire {de: 1, a: 6}") from e
        if not (0 <= masque[0] < masque[1] <= 24):
            raise ErreurConfig("politique.yaml : « tv_heures_masquees: » doit aller d'une heure à une heure plus tardive, entre 0 et 24")
    cas_douteux = politique.get("cas_douteux") or {}
    if not isinstance(cas_douteux, dict) or not all(
            isinstance(cas_douteux.get(r) or [], list) and all(isinstance(m, str) for m in cas_douteux.get(r) or [])
            for r in ("mots", "emissions_a_invites")):
        raise ErreurConfig("politique.yaml : « cas_douteux: » doit contenir des listes de textes « mots: » et « emissions_a_invites: »")
    liste_blanche = politique.get("liste_blanche") or {}
    if not isinstance(liste_blanche, dict):
        raise ErreurConfig("politique.yaml : « liste_blanche: » doit contenir des rubriques")

    for e in liste_blanche.get("emissions") or []:
        if not (isinstance(e, str) or (isinstance(e, dict) and isinstance(e.get("titre"), str))):
            raise ErreurConfig(f"politique.yaml, liste blanche : émission illisible {e!r} (texte ou {{titre: …, chaine: …}})")
    fonctions_politiques = politique.get("fonctions_politiques") or []
    if not isinstance(fonctions_politiques, list) or not all(isinstance(m, str) for m in fonctions_politiques):
        raise ErreurConfig("politique.yaml : « fonctions_politiques: » doit être une liste de textes")
    mots_presidentielle = (politique.get("presidentielle") or {}).get("mots") or []
    if not isinstance(mots_presidentielle, list) or not all(isinstance(m, str) for m in mots_presidentielle):
        raise ErreurConfig("politique.yaml : « presidentielle: mots: » doit être une liste de textes")
    noms_chaines = {c.nom for c in chaines}
    for nom in liste_blanche.get("chaines") or []:
        if nom not in noms_chaines:
            anomalies.append(f"politique.yaml, liste blanche : chaîne « {nom} » absente de chaines.yaml")

    return Configuration(
        chaines=chaines,
        candidats=candidats,
        personnalites=_liste_de_noms(politique, "personnalites", "politique.yaml"),
        partis=_liste_de_noms(politique, "partis", "politique.yaml"),
        liste_blanche=liste_blanche,
        mots_cles=mots_cles,
        mots_cles_titre=mots_cles_titre,
        tv_heures_masquees=masque,
        cas_douteux=cas_douteux,
        fonctions_politiques=fonctions_politiques,
        mots_presidentielle=mots_presidentielle,
        anomalies=anomalies,
    )
