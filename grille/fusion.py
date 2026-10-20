"""Dédoublonnage : une même diffusion vue sur plusieurs chaînes ou plateformes ne
fait qu'une émission, avec tous ses liens.

Deux émissions sont la même diffusion quand :
- elles viennent de chaînes différentes (ou de la même chaîne sur deux plateformes) ;
- elles commencent à moins de ECART_MAX l'une de l'autre (un direct Twitch annoncé
  à 14 h pour des Questions au gouvernement à 14 h 02) ;
- leurs titres concordent : titres identiques, ou tous les mots significatifs du
  titre le plus court (au moins deux) figurent dans l'autre (« Questions au
  gouvernement » et « Questions au Gouvernement à l'Assemblée »).

Rien n'est effacé en base : la fusion se fait à l'affichage (page, email, lister),
et une règle trop large se corrige ici sans perte.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from grille.filtre import normaliser

ECART_MAX = timedelta(minutes=20)
# Ordre de préférence pour l'émission qui porte la carte (chaîne, logo, titre).
PRIORITE = {"tv": 0, "radio": 1, "youtube": 2, "twitch": 3, "web": 4}
MOTS_VIDES = {
    "le", "la", "les", "l", "de", "du", "des", "d", "a", "au", "aux", "et", "en", "un", "une", "sur", "avec",
    "pour", "par", "dans", "ce", "cette", "son", "sa", "ses", "direct", "live", "replay", "integrale",
}


def _mots(titre: str) -> set[str]:
    return {m for m in normaliser(titre).split() if m not in MOTS_VIDES}


def meme_titre(a: str, b: str) -> bool:
    if normaliser(a) == normaliser(b) and normaliser(a):
        return True
    court, long_ = sorted((_mots(a), _mots(b)), key=len)
    return len(court) >= 2 and court <= long_


def _meme_diffusion(a: dict, b: dict) -> bool:
    ecart = abs(datetime.fromisoformat(a["debut"]) - datetime.fromisoformat(b["debut"]))
    # Même nom, autre plateforme (franceinfo à la télévision et à la radio) : deux diffuseurs.
    autre = (a["chaine"], a["plateforme"]) != (b["chaine"], b["plateforme"])
    return autre and ecart <= ECART_MAX and meme_titre(a["titre"], b["titre"])


def precision(titre: str, titre_de_tete: str) -> str:
    """Ce qui distingue une version de la diffusion principale, quand son titre la
    prolonge après un séparateur : « … Clermont-Ferrand - Vélotypie et LSF » → « Vélotypie et LSF »."""
    if not titre.casefold().startswith(titre_de_tete.casefold()):
        return ""
    reste = titre[len(titre_de_tete):]
    if not reste.lstrip()[:1] in ("-", "—", "–", "|", ":", "(", "[", "·"):
        return ""
    return reste.strip().lstrip("-—–|:([·").rstrip(")]").strip()


def _representant(groupe: list[dict]) -> dict:
    return min(groupe, key=lambda e: (PRIORITE.get(e["plateforme"], 9), e["filtre"] != "liste blanche",
                                      len(e["titre"]), e["debut"]))


def fusionner(emissions: list[dict]) -> list[dict]:
    """Regroupe les doublons. Chaque émission fusionnée garde les champs de son
    représentant, réunit invités et liens, et liste ses `sources` (chaîne,
    plateforme, liens), représentant en premier. Une émission seule est rendue telle quelle."""
    groupes: list[list[dict]] = []
    for e in sorted(emissions, key=lambda e: e["debut"]):
        for groupe in groupes:
            # Jamais deux émissions de la même chaîne (sur la même plateforme) dans un groupe.
            if all((m["chaine"], m["plateforme"]) != (e["chaine"], e["plateforme"]) for m in groupe) \
                    and any(_meme_diffusion(m, e) for m in groupe):
                groupe.append(e)
                break
        else:
            groupes.append([e])

    resultat = []
    for groupe in groupes:
        if len(groupe) == 1:
            resultat.append(groupe[0])
            continue
        tete = _representant(groupe)
        membres = [tete] + [m for m in groupe if m is not tete]
        fusion = dict(tete)
        fusion["invites"] = list(dict.fromkeys(nom for m in membres for nom in m["invites"]))
        fusion["cites"] = list(dict.fromkeys(nom for m in membres for nom in m.get("cites") or []))
        fusion["lien"] = list(dict.fromkeys(url for m in membres for url in m["lien"]))
        if any(m["statut"] == "en direct" for m in membres):
            fusion["statut"] = "en direct"
        if any(m["filtre"] == "liste blanche" for m in membres):
            fusion["filtre"] = "liste blanche"
        fusion["sources"] = [{"chaine": m["chaine"], "plateforme": m["plateforme"], "lien": m["lien"],
                              "precision": precision(m["titre"], tete["titre"])} for m in membres]
        resultat.append(fusion)
    return sorted(resultat, key=lambda e: (datetime.fromisoformat(e["debut"]), e["chaine"]))
