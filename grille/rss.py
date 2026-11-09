"""Mesure des flux RSS (presse, chaînes, sites médias) : annoncent-ils des passages médias
que la grille ne connaît pas encore ? (« Marine Tondelier invitée du 20 h de TF1 » : article
TF1info de 15 h 50 le 9 novembre 2026, invisible pour le guide et pour la recherche par Claude.)

Phase de mesure : rien n'est ajouté à la grille. À chaque collecte, les flux de config/rss.yaml
sont relus ; un article est une annonce probable quand il nomme une personne de politique.yaml,
une chaîne de télévision ou de radio de chaines.yaml et un mot de passage média (« invité »,
« sur le plateau », « au 20h »…). Il est noté une fois (table `rss_annonces`), avec l'heure de
publication, l'heure où la collecte l'a vu et si la grille connaissait déjà ce passage
(personne présente dans une émission de la même chaîne, de la veille au lendemain). L'email
du matin en fait le compte, pour décider ensuite de brancher ou non ces flux.

Nouveaux candidats : un article qui annonce une candidature (« annonce sa candidature »,
« candidat à la présidentielle », « se lance dans la course à l'Élysée ») et nomme une personne
absente de politique.yaml est noté (table `rss_candidats`). L'email propose les noms vus dans
plusieurs articles, avec la ligne à copier dans politique.yaml : l'ajout reste une décision
humaine (candidatures envisagées, rumeurs, commentateurs nommés dans l'article).
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import requests

from grille import affichage, db
from grille.config import Configuration
from grille.filtre import FiltrePolitique, normaliser
from grille.tv import PARIS

DELAI = 20
EN_TETES = {"User-Agent": "Mozilla/5.0 (compatible; grille-politique-2027; mesure de flux RSS)"}
RECENT = timedelta(hours=36)  # articles plus anciens ignorés
# Mots d'un passage média (texte normalisé, sans accents).
_PASSAGE = re.compile(
    r"\b(invite|invitee|invites|invitees|sera l invite|plateau|face a|interview|interviewe|interviewee|entretien|"
    r"au 20h|au 20 heures|au 13h|au 13 heures|journal de 20|journal de 13|ce soir sur|ce matin sur|demain sur|"
    r"dans l emission|matinale|grand oral|grand jury|questions politiques|repondra|repond aux questions|"
    r"sur le plateau de)\b")


# Annonce d'une candidature à la présidentielle (texte normalisé).
_CANDIDATURE = re.compile(
    r"\b(annonce|officialise|declare|confirme|lance) sa candidature|"
    r"\bcandidat(e|s|es)? (a|pour) (la presidentielle|l election presidentielle|l elysee|la presidence)|"
    r"\bcandidature (a|pour) (la presidentielle|l election presidentielle|l elysee)|"
    r"\b(course|candidat|candidate) a l elysee|\bse (lance|declare|porte candidat|presente) (dans la course|a la presidentielle|a l election presidentielle)")
# « Prénom Nom » (deux ou trois mots en capitale, particule permise) dans le texte d'origine.
_MAJ = "A-ZÀÂÄÇÉÈÊËÎÏÔÖÙÛÜ"
_NOM_PROPRE = re.compile(
    rf"\b([{_MAJ}][a-zà-ÿ]+(?:-[{_MAJ}][a-zà-ÿ]+)?)\s+((?:(?:de|du|des|d'|le|la)\s?)?[{_MAJ}][a-zà-ÿA-Z'-]+"
    rf"(?:\s+[{_MAJ}][a-zà-ÿ'-]+)?)")
# Premiers mots qui ne sont pas des prénoms (débuts de phrase, lieux, institutions…).
_PAS_PRENOM = {
    "presidentielle", "election", "elysee", "france", "paris", "assemblee", "senat", "gouvernement", "premier",
    "le", "la", "les", "un", "une", "des", "du", "de", "pour", "avec", "selon", "apres", "avant", "quand", "comment",
    "pourquoi", "ce", "cette", "il", "elle", "ils", "elles", "on", "nous", "vous", "je", "mais", "et", "ou", "si",
    "en", "au", "aux", "sur", "dans", "par", "parti", "republique", "etat", "europe", "union", "front", "nouveau",
    "nouvelle", "rassemblement", "renaissance", "horizons", "reconquete", "ecologistes", "socialiste", "direct",
    "video", "sondage", "candidat", "candidate", "candidature", "campagne", "judoka", "ancien", "ancienne", "ministre",
    "maire", "depute", "deputee", "senateur", "senatrice", "president", "presidente", "chef", "leader", "patron",
    # Lieux en deux mots (« Los Angeles », « Saint-Denis » est déjà un seul mot).
    "los", "las", "san", "santa", "new", "saint", "sainte", "porto", "buenos", "hong", "rio", "tel",
}


@dataclass
class Rapport:
    flux_lus: int = 0
    articles: int = 0
    nouvelles: list[dict] = field(default_factory=list)  # annonces probables vues pour la première fois
    candidats: list[dict] = field(default_factory=list)  # (nom, article) de candidatures possibles, nouveaux
    anomalies: list[str] = field(default_factory=list)


def _texte(fragment: str | None) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).split())


def _date(valeur: str | None) -> datetime | None:
    if not valeur:
        return None
    valeur = valeur.strip()
    try:
        d = parsedate_to_datetime(valeur)  # RSS : « Mon, 09 Nov 2026 15:50:00 +0100 »
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(valeur.replace("Z", "+00:00"))  # Atom : ISO 8601
        except ValueError:
            return None
    return (d if d.tzinfo else d.replace(tzinfo=PARIS)).astimezone(PARIS)


def lire_flux(contenu: bytes) -> list[dict]:
    """Articles d'un flux RSS 2.0 ou Atom : titre, résumé, lien, identifiant, date de publication."""
    racine = ET.fromstring(contenu)
    articles = []
    for noeud in racine.iter():
        if noeud.tag.split("}")[-1] not in ("item", "entry"):
            continue
        champs: dict[str, str] = {}
        for c in noeud:
            nom = c.tag.split("}")[-1]
            if nom == "link" and c.get("href"):
                champs.setdefault("link", c.get("href"))
            elif c.text and nom not in champs:
                champs[nom] = c.text
        lien = (champs.get("link") or "").strip()
        articles.append({
            "titre": _texte(champs.get("title")),
            "resume": _texte(champs.get("description") or champs.get("summary") or champs.get("content")),
            "lien": lien,
            "id": (champs.get("guid") or champs.get("id") or lien).strip(),
            "publie": _date(champs.get("pubDate") or champs.get("published") or champs.get("updated")
                            or champs.get("date")),
        })
    return articles


def _chaines(config: Configuration) -> list[tuple[str, str]]:
    """(nom affiché, forme normalisée) des chaînes de télévision et de radio, sans doublon."""
    vues: dict[str, str] = {}
    for c in config.chaines:
        if c.plateforme in ("tv", "radio"):
            nom = re.sub(r"\s*\((tv|radio)\)$", "", c.nom)
            for forme in {nom, *nom.split(" / ")}:
                vues.setdefault(normaliser(forme), forme)
    return [(nom, forme) for forme, nom in vues.items() if forme]


def annonce(article: dict, filtre: FiltrePolitique, chaines: list[tuple[str, str]]) -> dict | None:
    """Personnes et chaînes d'une annonce probable de passage média, ou None."""
    texte = f"{article['titre']}. {article['resume']}"
    texte_n = normaliser(texte)
    if not _PASSAGE.search(texte_n):
        return None
    personnes = filtre.personnes_nommees(texte)
    nommees = [nom for nom, forme in chaines if f" {forme} " in f" {texte_n} "]
    if not personnes or not nommees:
        return None
    return {"personnes": personnes, "chaines": nommees}


def noms_connus(config: Configuration) -> set[str]:
    """Noms complets et alias de politique.yaml (candidats et personnalités), normalisés."""
    return {normaliser(f) for p in config.candidats + config.personnalites for f in [p["nom"]] + list(p.get("alias") or [])}


def candidats_possibles(article: dict, connus: set[str]) -> list[str]:
    """Personnes absentes de politique.yaml nommées dans un article qui annonce une candidature."""
    titre, resume = article["titre"], article["resume"]
    texte_n = normaliser(f"{titre}. {resume}")
    # Formule explicite, ou article sur la présidentielle qui parle d'une candidature
    # (« Teddy Riner candidat à l'élection », « les réactions à la candidature de… »).
    if not (_CANDIDATURE.search(texte_n)
            or ("presidentielle" in texte_n and re.search(r"\bcandidat(e|s|es|ure)?\b", texte_n))):
        return []
    noms = []
    # Le titre et la première phrase du résumé : c'est là que le candidat est nommé.
    for texte in (titre, re.split(r"(?<=[.!?])\s", resume)[0] if resume else ""):
        for m in _NOM_PROPRE.finditer(texte):
            prenom, reste = m.group(1), m.group(2)
            nom = f"{prenom} {reste}".strip()
            mots = normaliser(nom).split()
            if normaliser(prenom) in _PAS_PRENOM or len(mots) < 2:
                continue
            # Déjà connu, en entier ou par son nom de famille (alias).
            if normaliser(nom) in connus or normaliser(reste) in connus or any(
                    f" {c} " in f" {normaliser(nom)} " for c in connus if len(c.split()) >= 2):
                continue
            noms.append(nom)
    return list(dict.fromkeys(noms))


def deja_en_grille(emissions: list[dict], personnes: list[str], chaines: list[str]) -> bool:
    """La grille montre déjà une de ces personnes dans une émission d'une de ces chaînes."""
    chaines_n = {normaliser(c) for c in chaines}
    for e in emissions:
        noms = {normaliser(s["chaine"]) for s in e.get("sources") or []} | {normaliser(e["chaine"])}
        noms |= {n for nom in list(noms) for n in nom.split(" / ")}
        if noms & chaines_n and set(e["invites"]) & set(personnes):
            return True
    return False


def collecter(config: Configuration, session: requests.Session, connexion, maintenant: datetime) -> Rapport:
    rapport = Rapport()
    maintenant = maintenant.astimezone(PARIS)
    filtre = FiltrePolitique(config)
    chaines = _chaines(config)
    grille = affichage.emissions(connexion, maintenant - timedelta(days=1), maintenant + timedelta(days=2))
    connues = db.rss_ids(connexion)
    connus = noms_connus(config)
    candidats_vus = db.rss_candidats_ids(connexion)
    for flux in config.rss:
        try:
            r = session.get(flux["adresse"], headers=EN_TETES, timeout=DELAI)
            r.raise_for_status()
            articles = lire_flux(r.content)
        except (requests.RequestException, ET.ParseError) as e:
            rapport.anomalies.append(f"flux illisible : {flux['nom']} ({type(e).__name__})")
            continue
        rapport.flux_lus += 1
        for a in articles:
            if not a["id"] or a["id"] in connues or (a["publie"] and a["publie"] < maintenant - RECENT):
                continue
            rapport.articles += 1
            for nom in candidats_possibles(a, connus):
                if (nom, a["id"]) not in candidats_vus:
                    candidats_vus.add((nom, a["id"]))
                    rapport.candidats.append({"nom": nom, "id": a["id"], "flux": flux["nom"], "titre": a["titre"],
                                              "lien": a["lien"], "vu_le": maintenant.isoformat(timespec="seconds")})
            trouve = annonce(a, filtre, chaines)
            if trouve is None:
                continue
            connues.add(a["id"])
            rapport.nouvelles.append({
                "id": a["id"], "flux": flux["nom"], "titre": a["titre"], "lien": a["lien"],
                "publie": a["publie"].isoformat(timespec="seconds") if a["publie"] else "",
                "vu_le": maintenant.isoformat(timespec="seconds"),
                "personnes": trouve["personnes"], "chaines": trouve["chaines"],
                "deja_en_grille": deja_en_grille(grille, trouve["personnes"], trouve["chaines"]),
            })
    db.noter_rss(connexion, rapport.nouvelles, maintenant)
    db.noter_rss_candidats(connexion, rapport.candidats, maintenant)
    return rapport
