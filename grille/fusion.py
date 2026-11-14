"""Dédoublonnage : une même diffusion vue sur plusieurs chaînes ou plateformes ne
fait qu'une émission, avec tous ses liens.

Deux émissions sont la même diffusion quand :
- elles viennent de chaînes différentes (ou de la même chaîne sur deux plateformes) ;
- elles commencent à moins de ECART_MAX l'une de l'autre (un direct Twitch annoncé
  à 14 h pour des Questions au gouvernement à 14 h 02) ;
- leurs titres concordent : titres identiques, ou tous les mots significatifs du
  titre le plus court (au moins deux) figurent dans l'autre (« Questions au
  gouvernement » et « Questions au Gouvernement à l'Assemblée ») ;
- ou bien c'est le même émetteur sur deux plateformes (La France insoumise sur YouTube
  et sur Twitch), à moins de ECART_EMETTEUR d'écart, avec au moins deux mots
  significatifs en commun : chaque plateforme a son titre (« Réunion publique à
  Rochefort | Présidentielle 2027 » et « Réunion publique à Rochefort avec Mathilde
  Panot et Antoine Léaument »).

Rien n'est effacé en base : la fusion se fait à l'affichage (page, email, lister),
et une règle trop large se corrige ici sans perte.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from grille.filtre import normaliser

ECART_MAX = timedelta(minutes=20)
PREFIXE_EVENEMENT = "evenement:"  # config/evenements.yaml (grille/evenements.py)
# Émissions ajoutées par-dessus les collecteurs : événements écrits à la main, grandes émissions
# surveillées dont Claude a trouvé l'invité (grille/invites_web.py). Quand la même diffusion est
# déjà dans la grille, elles la complètent au lieu de faire une deuxième carte.
PREFIXES_COMPLEMENTS = (PREFIXE_EVENEMENT, "recherche:")
ECART_EMETTEUR = timedelta(minutes=10)
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
    if not autre or ecart > ECART_MAX:
        return False
    if meme_titre(a["titre"], b["titre"]):
        return True
    meme_emetteur = normaliser(a["chaine"]) == normaliser(b["chaine"])
    if not meme_emetteur or ecart > ECART_EMETTEUR:
        return False
    # Titre court de l'émission repris tel quel dans le titre de l'autre plateforme : « Face à
    # Face » (RMC, radio) et « EN DIRECT - Dominique de Villepin est l'invité du Face à Face
    # d'Apolline de Malherbe » (RMC, YouTube), 10 novembre 2026.
    court, long_ = sorted((normaliser(a["titre"]), normaliser(b["titre"])), key=len)
    if len(court.split()) >= 2 and f" {court} " in f" {long_} ":
        return True
    # Le nom de l'émetteur ne compte pas (« … sur Sud Radio » / « L'invité politique Sud Radio »).
    communs = _mots(a["titre"]) & _mots(b["titre"]) - _mots(a["chaine"])
    return len(communs) >= 2


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


def complete(complement: dict, e: dict) -> bool:
    """L'ajout (événement écrit à la main, émission surveillée) annonce l'invité d'une émission déjà
    dans la grille, sur la même chaîne : « Franc-jeu — Laurent Wauquiez » pour « Franc-jeu du
    dimanche 08 novembre » ou « Le député Laurent Wauquiez, invité de Franc-Jeu » ; « L'invité de
    8h20 : le grand entretien — Gabriel Attal » (recherche) et la même diffusion vue par Radio France."""
    if (e["chaine"], e["plateforme"]) != (complement["chaine"], complement["plateforme"]) \
            or str(e["id"]).startswith(PREFIXES_COMPLEMENTS):
        return False
    ecart = abs(datetime.fromisoformat(e["debut"]) - datetime.fromisoformat(complement["debut"]))
    nom = normaliser(complement["titre"].split(" — ")[0])
    # Le nom de l'émission n'importe où dans le titre : Radio France renomme parfois la diffusion
    # une fois l'invité connu (« Le député Laurent Wauquiez, invité de Franc-Jeu »).
    return ecart <= ECART_MAX and bool(nom) and f" {nom} " in f" {normaliser(e['titre'])} "


def avec_evenements(emissions: list[dict]) -> list[dict]:
    """Un ajout qui complète une émission déjà connue (son invité annoncé en direct, ou trouvé par
    Claude) ne fait pas une deuxième carte : ses invités et son résumé passent sur l'émission."""
    reste = [e for e in emissions if not str(e["id"]).startswith(PREFIXES_COMPLEMENTS)]
    resultat = list(reste)
    for ev in (e for e in emissions if str(e["id"]).startswith(PREFIXES_COMPLEMENTS)):
        cible = next((i for i, e in enumerate(resultat) if complete(ev, e)), None)
        if cible is None or ev["statut"] == "annulé":
            if cible is None:
                resultat.append(ev)
            continue
        e = dict(resultat[cible])
        e["invites"] = list(dict.fromkeys(list(e["invites"]) + list(ev["invites"])))
        e["cites"] = [n for n in dict.fromkeys(list(e.get("cites") or []) + list(ev.get("cites") or []))
                      if n not in e["invites"]]
        if ev.get("resume") and not e.get("resume"):
            e["resume"] = ev["resume"]
        resultat[cible] = e
    return resultat


def fusionner(emissions: list[dict]) -> list[dict]:
    """Regroupe les doublons. Chaque émission fusionnée garde les champs de son
    représentant, réunit invités et liens, et liste ses `sources` (chaîne,
    plateforme, liens), représentant en premier. Une émission seule est rendue telle quelle."""
    emissions = avec_evenements(emissions)
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
    # Les groupes formés dans l'ordre des heures peuvent encore se rejoindre : France Inter
    # (13 h 19) ne ressemble pas au direct YouTube (13 h 19) mais bien à France 2 (13 h 20),
    # arrivée ensuite dans le groupe du direct (Franc-jeu, 8 novembre 2026).
    fusion_faite = True
    while fusion_faite:
        fusion_faite = False
        for i, a in enumerate(groupes):
            for b in groupes[i + 1:]:
                if not {(m["chaine"], m["plateforme"]) for m in a} & {(m["chaine"], m["plateforme"]) for m in b} \
                        and any(_meme_diffusion(x, y) for x in a for y in b):
                    a.extend(b)
                    groupes.remove(b)
                    fusion_faite = True
                    break
            if fusion_faite:
                break

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
