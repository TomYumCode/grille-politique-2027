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
_LISTE_YOUTUBE = re.compile(r"^(PL|UU|OL)[\w-]{8,}$")
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
    # YouTube : épisodes de séries politiques publiés en vidéos ordinaires (ni direct ni première).
    # Identifiants de listes de lecture (PL…), ou « toutes » pour toutes les vidéos de la chaîne.
    episodes: tuple[str, ...] = ()


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
    # Événements ajoutés à la main (config/evenements.yaml, grille/evenements.py).
    evenements: list[dict] = field(default_factory=list)
    # Adresse du service de notifications (config/notifications.yaml) ; vide : pas de notifications.
    notifications: str = ""
    # Invité cherché sur le web par Claude (config/recherche.yaml, grille/invites_web.py).
    recherche: dict = field(default_factory=dict)
    # Flux RSS mesurés (config/rss.yaml, grille/rss.py) : [{"nom", "adresse"}].
    rss: list[dict] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)

    def candidats_officiels(self) -> set[str]:
        """Candidats déclarés ou désignés (statut « déclaré… », « désigné… » dans politique.yaml),
        sans les pressentis ni les « à vérifier »."""
        return {c["nom"] for c in self.candidats
                if str(c.get("statut", "")).lower().startswith(("déclar", "désign"))}

    def equipes_de_campagne(self) -> set[str]:
        """Personnalités marquées « campagne: true » : porte-parole et équipes des candidats."""
        return {p["nom"] for p in self.personnalites if p.get("campagne")}

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
        brut = ligne.get("episodes") or []
        episodes = []
        for e in [brut] if isinstance(brut, str) else brut:
            e = str(e).strip()
            if plateforme == "youtube" and (e == "toutes" or _LISTE_YOUTUBE.match(e)):
                episodes.append(e)
            else:
                anomalies.append(f"{etiquette} : « episodes » invalide « {e} » (liste de lecture PL… ou « toutes »), ignoré")
        vues.add((plateforme, adresse.lower()))
        chaines.append(
            Chaine(
                plateforme, nom, adresse, str(ligne["categorie"]).strip(), bool(ligne.get("a_confirmer")), direct,
                logo, cle, tuple(episodes)
            )
        )
    return chaines


def _liste_de_noms(contenu: dict, rubrique: str, fichier: str) -> list[dict]:
    entrees = contenu.get(rubrique) or []
    if not isinstance(entrees, list) or not all(isinstance(e, dict) and e.get("nom") for e in entrees):
        raise ErreurConfig(f"{fichier} : chaque entrée de « {rubrique}: » doit avoir un « nom »")
    return entrees


def _lire_evenements(chemin: Path, anomalies: list[str]) -> list[dict]:
    """Événements ajoutés à la main : fichier facultatif, une ligne fautive est signalée et ignorée."""
    if not chemin.exists():
        return []
    evenements = []
    for i, ligne in enumerate(_lire_yaml(chemin).get("evenements") or [], start=1):
        if not isinstance(ligne, dict) or not ligne.get("titre") or not ligne.get("debut") or not ligne.get("chaines"):
            anomalies.append(f"evenements.yaml, événement n° {i} : « titre », « debut » et « chaines » sont obligatoires")
            continue
        evenements.append(ligne)
    return evenements


def _lire_notifications(chemin: Path, anomalies: list[str]) -> str:
    """Adresse https du service de notifications, terminée par « / » ; vide si absente."""
    if not chemin.exists():
        return ""
    adresse = str(_lire_yaml(chemin).get("adresse") or "").strip()
    if adresse and not re.fullmatch(r"https://[\w.-]+(/[\w./-]*)?", adresse):
        anomalies.append(f"notifications.yaml : adresse invalide « {adresse} », notifications désactivées")
        return ""
    return adresse if not adresse or adresse.endswith("/") else adresse + "/"


RECHERCHE_DEFAUT = {"actif": False, "modele": "claude-opus-5-5", "recherches_par_jour": 12, "avant_debut": 10,
                    "apres_debut": 35, "heure_annonces": "17:00", "a_surveiller": []}
_HEURE = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


def _lire_recherche(chemin: Path, anomalies: list[str]) -> dict:
    """Réglages de la recherche d'invités par Claude ; absents : recherche arrêtée."""
    if not chemin.exists():
        return dict(RECHERCHE_DEFAUT)
    brut = _lire_yaml(chemin)
    reglages = dict(RECHERCHE_DEFAUT, actif=brut.get("actif") is True)
    modele = str(brut.get("modele") or RECHERCHE_DEFAUT["modele"]).strip()
    if not re.fullmatch(r"claude-[a-z0-9-]+", modele):
        anomalies.append(f"recherche.yaml : modèle illisible « {modele} », recherche arrêtée")
        return dict(reglages, actif=False)
    reglages["modele"] = modele
    for cle in ("recherches_par_jour", "avant_debut", "apres_debut"):
        if cle in brut:
            try:
                reglages[cle] = max(0, int(brut[cle]))
            except (TypeError, ValueError):
                anomalies.append(f"recherche.yaml : « {cle} » doit être un nombre, {RECHERCHE_DEFAUT[cle]} gardé")
    heure = str(brut.get("heure_annonces") or RECHERCHE_DEFAUT["heure_annonces"]).strip()
    if _HEURE.fullmatch(heure):
        reglages["heure_annonces"] = heure
    else:
        anomalies.append(f"recherche.yaml : « heure_annonces » illisible « {heure} » (écrire 17:00), 17:00 gardé")
    surveillees = []
    for i, s in enumerate(brut.get("a_surveiller") or [], 1):
        if not (isinstance(s, dict) and s.get("titre") and s.get("chaine") and _HEURE.fullmatch(str(s.get("heure")))):
            anomalies.append(f"recherche.yaml, émission à surveiller n° {i} : « titre », « chaine » et « heure » "
                             "(20:00) sont obligatoires")
            continue
        # « chaine » : un nom, ou une liste pour une émission diffusée en même temps sur plusieurs
        # chaînes (« L'heure des pros » sur CNews et Europe 1) : une seule question, une ligne par chaîne.
        noms = [str(c) for c in s["chaine"]] if isinstance(s["chaine"], list) else [str(s["chaine"])]
        surveillees.append({"titre": str(s["titre"]), "chaine": noms[0], "chaines": noms, "heure": str(s["heure"]),
                            "duree": int(s.get("duree") or 45)})
    reglages["a_surveiller"] = surveillees
    return reglages


def _lire_rss(chemin: Path, anomalies: list[str]) -> list[dict]:
    if not chemin.exists():
        return []
    flux = []
    for i, f in enumerate(_lire_yaml(chemin).get("flux") or [], 1):
        adresse = str((f or {}).get("adresse") or "").strip() if isinstance(f, dict) else ""
        if not (isinstance(f, dict) and f.get("nom") and re.fullmatch(r"https://\S+", adresse)):
            anomalies.append(f"rss.yaml, flux n° {i} : « nom » et « adresse » (https://…) sont obligatoires")
            continue
        flux.append({"nom": str(f["nom"]), "adresse": adresse})
    return flux


def _verifier_surveillees(reglages: dict, chaines: list, anomalies: list[str]) -> dict:
    """Une émission à surveiller doit nommer une chaîne de chaines.yaml (pour son lien direct)."""
    noms = {c.nom for c in chaines if c.plateforme in ("tv", "radio")}
    gardees = []
    for s in reglages["a_surveiller"]:
        for nom in s["chaines"]:
            if nom not in noms:
                anomalies.append(f"recherche.yaml : chaîne inconnue « {nom} » (nom de chaines.yaml)")
        connues = [nom for nom in s["chaines"] if nom in noms]
        if connues:
            gardees.append(dict(s, chaine=connues[0], chaines=connues))
    return dict(reglages, a_surveiller=gardees)


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
        evenements=_lire_evenements(dossier / "evenements.yaml", anomalies),
        notifications=_lire_notifications(dossier / "notifications.yaml", anomalies),
        recherche=_verifier_surveillees(_lire_recherche(dossier / "recherche.yaml", anomalies), chaines, anomalies),
        rss=_lire_rss(dossier / "rss.yaml", anomalies),
        anomalies=anomalies,
    )
