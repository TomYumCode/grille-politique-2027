"""Invité cherché sur le web par Claude, au début d'une émission politique dont l'invité
est encore inconnu : BFMTV, LCI ou CNews ne l'annoncent nulle part où la grille peut le lire
(« Le grand oral 2027 », 8 novembre 2026 : Raphaël Glucksmann, ajouté à la main).

À chaque collecte (rapide ou complète), pour chaque émission à invité de la télévision ou de
la radio qui commence dans les `avant_debut` minutes ou a commencé depuis moins de
`apres_debut` minutes, sans invité connu, Claude cherche sur le web (outil de recherche de
l'API) et répond par un objet JSON. Garde-fous :
- un nom n'est retenu que s'il est dans politique.yaml (candidats, personnalités) ; un nom
  inconnu est seulement signalé dans le compte rendu de la collecte ;
- la page citée comme source doit faire partie des résultats de la recherche ;
- deux essais au plus par émission (le second après le début, au moins 15 minutes plus tard),
  et un plafond de questions par jour (config/recherche.yaml) : le coût reste borné.

Le résultat va dans la table `annonces` (identifiant « web:… »), appliquée à l'affichage
comme les communiqués de France Télévisions : la base des émissions n'est jamais modifiée.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from grille import affichage, db
from grille.config import Configuration
from grille.filtre import CRENEAU_INVITE, LISTE_BLANCHE, normaliser
from grille.tv import PARIS

SANS_CLE = "clé ANTHROPIC_API_KEY absente"
ESSAIS_MAX = 2
ECART_ESSAIS = timedelta(minutes=15)
RECHERCHES_WEB = 3  # recherches web au plus par question
REPRISES = 2  # « pause_turn » : la recherche côté serveur reprend au plus deux fois
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]

SYSTEME = """\
Tu aides une grille des émissions politiques françaises (télévision, radio). On te donne une \
émission qui commence ou vient de commencer. Cherche sur le web qui en est l'invité, ou les \
invités, pour cette diffusion précise (cette chaîne, ce jour) : annonce de la chaîne ou de \
l'animateur, article de presse, programme du jour, extrait publié pendant l'émission.

Ne devine jamais. Une page qui parle d'une autre diffusion (un autre jour, une autre chaîne) ne \
compte pas. Si aucune page trouvée ne nomme l'invité de cette diffusion, réponds sans invité. \
Les journalistes, animateurs et chroniqueurs de l'émission ne sont pas des invités.

Termine ta réponse par un seul objet JSON, sans rien après :
{"invites": ["Prénom Nom"], "source": "adresse de la page qui le dit", "extrait": "phrase de la page qui le dit"}
Sans invité trouvé : {"invites": [], "source": "", "extrait": ""}"""


@dataclass
class Rapport:
    cherchees: int = 0
    trouvees: list[tuple[str, list[str]]] = field(default_factory=list)  # (titre, invités retenus)
    inconnus: list[str] = field(default_factory=list)  # noms trouvés absents de politique.yaml
    plafond_atteint: bool = False
    anomalies: list[str] = field(default_factory=list)
    interrompu: str = ""
    jetons: dict = field(default_factory=lambda: {"entree": 0, "sortie": 0, "recherches": 0})


def emission_a_invite(e: dict, config: Configuration) -> bool:
    """Émission de plateau ou d'interview, d'après la liste blanche ou son titre."""
    if e["plateforme"] not in ("tv", "radio") or e.get("nature") == "episode":
        return False
    if e["filtre"] == LISTE_BLANCHE and e["categorie"] in ("interview", "débat"):
        return True
    titre = normaliser(e["titre"])
    return bool(CRENEAU_INVITE.search(titre)) or any(
        titre.startswith(normaliser(x)) for x in (config.cas_douteux.get("emissions_a_invites") or []))


def a_chercher(e: dict, config: Configuration, connexion, maintenant: datetime) -> bool:
    if e["statut"] == "annulé" or e["invites"] or not emission_a_invite(e, config):
        return False
    debut = datetime.fromisoformat(e["debut"])
    reglages = config.recherche
    if not debut - timedelta(minutes=reglages["avant_debut"]) <= maintenant <= \
            debut + timedelta(minutes=reglages["apres_debut"]):
        return False
    deja = db.recherche_invites(connexion, e["id"])
    if deja is None:
        return True
    # Second essai : seulement après le début, quand la chaîne a pu publier l'invité.
    return (deja["essais"] < ESSAIS_MAX and not deja["invites"] and maintenant >= debut
            and maintenant - deja["derniere"] >= ECART_ESSAIS)


def question(e: dict) -> str:
    debut = datetime.fromisoformat(e["debut"]).astimezone(PARIS)
    fin = datetime.fromisoformat(e["fin"]).astimezone(PARIS) if e.get("fin") else None
    support = "télévision" if e["plateforme"] == "tv" else "radio"
    chaines = [s["chaine"] for s in e.get("sources") or []] or [e["chaine"]]
    horaire = f"de {debut:%H:%M} à {fin:%H:%M}" if fin else f"à {debut:%H:%M}"
    lignes = [
        f"Émission : {e['titre']}",
        f"Chaîne : {', '.join(dict.fromkeys(chaines))} ({support})",
        f"Diffusion : {JOURS[debut.weekday()]} {debut.day} {MOIS[debut.month - 1]} {debut.year}, "
        f"{horaire} (heure de Paris)",
    ]
    if (e.get("resume") or "").strip():
        lignes.append(f"Présentation de la chaîne : {' '.join(e['resume'].split())[:600]}")
    return "\n".join(lignes)


def outil_recherche(modele: str) -> dict:
    """Recherche web avec filtrage des résultats (Opus et Sonnet), sinon la version de base."""
    lieu = {"type": "approximate", "country": "FR", "timezone": "Europe/Paris"}
    version = "web_search_20260209" if re.match(r"claude-(opus|sonnet)-", modele) else "web_search_20250305"
    return {"type": version, "name": "web_search", "max_uses": RECHERCHES_WEB, "user_location": lieu}


def _adresses(objet) -> set[str]:
    """Toutes les adresses de pages présentes dans la réponse (résultats, citations)."""
    trouvees: set[str] = set()
    if isinstance(objet, dict):
        for cle, valeur in objet.items():
            if cle == "url" and isinstance(valeur, str):
                trouvees.add(valeur)
            else:
                trouvees |= _adresses(valeur)
    elif isinstance(objet, list):
        for valeur in objet:
            trouvees |= _adresses(valeur)
    return trouvees


def lire_reponse(contenu: list[dict]) -> tuple[list[str], str, set[str]]:
    """(noms, source, adresses des résultats) d'après les blocs de la réponse. Le dernier
    objet JSON du texte final est la réponse ; illisible : aucun invité."""
    adresses = _adresses(contenu)
    texte = "".join(b.get("text", "") for b in contenu if b.get("type") == "text")
    for m in reversed(list(re.finditer(r"\{[^{}]*\"invites\"[^{}]*\}", texte, re.DOTALL))):
        try:
            donnees = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        noms = [str(n).strip() for n in donnees.get("invites") or [] if str(n).strip()]
        return noms, str(donnees.get("source") or "").strip(), adresses
    return [], "", adresses


def _noms_connus(config: Configuration) -> dict[str, str]:
    """Forme normalisée (nom complet ou alias) → nom de politique.yaml."""
    connus: dict[str, str] = {}
    for p in config.candidats + config.personnalites:
        for forme in [p["nom"]] + list(p.get("alias") or []):
            connus.setdefault(normaliser(forme), p["nom"])
    return connus


def _meme_page(a: str, b: str) -> bool:
    return a.rstrip("/").split("#")[0] == b.rstrip("/").split("#")[0]


def demander(client, modele: str, e: dict, rapport: Rapport) -> list[dict]:
    """Pose la question ; renvoie les blocs de la réponse finale (dictionnaires)."""
    messages = [{"role": "user", "content": question(e)}]
    for _ in range(REPRISES + 1):
        reponse = client.beta.messages.create(
            model=modele,
            max_tokens=8000,
            # Refus d'un filtre de sécurité : la même question passe à un autre modèle.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low"},
            system=SYSTEME,
            tools=[outil_recherche(modele)],
            messages=messages,
        )
        usage = reponse.usage
        rapport.jetons["entree"] += usage.input_tokens or 0
        rapport.jetons["sortie"] += usage.output_tokens or 0
        outils = getattr(usage, "server_tool_use", None)
        rapport.jetons["recherches"] += (getattr(outils, "web_search_requests", 0) or 0) if outils else 0
        contenu = [b.to_dict() for b in reponse.content]
        if reponse.stop_reason != "pause_turn":
            return [] if reponse.stop_reason == "refusal" else contenu
        # Recherche côté serveur en pause : la renvoyer telle quelle, elle reprend.
        messages = messages[:1] + [{"role": "assistant", "content": contenu}]
    return []


def _client(cle: str):
    import anthropic  # seulement quand une recherche est à faire

    return anthropic.Anthropic(api_key=cle, timeout=180, max_retries=2)


def collecter(config: Configuration, connexion, maintenant: datetime, client=None) -> Rapport:
    rapport = Rapport()
    reglages = config.recherche
    if not reglages.get("actif"):
        rapport.interrompu = "recherche arrêtée (config/recherche.yaml)"
        return rapport
    maintenant = maintenant.astimezone(PARIS)
    candidates = [e for e in affichage.emissions(connexion, maintenant - timedelta(hours=2),
                                                  maintenant + timedelta(hours=1))
                  if a_chercher(e, config, connexion, maintenant)]
    if not candidates:
        return rapport
    if client is None:
        cle = os.environ.get("ANTHROPIC_API_KEY")
        if not cle:
            rapport.interrompu = SANS_CLE
            return rapport
        client = _client(cle)
    import anthropic

    connus = _noms_connus(config)
    for e in candidates:
        if db.recherches_du_jour(connexion, maintenant) >= reglages["recherches_par_jour"]:
            rapport.plafond_atteint = True
            break
        try:
            contenu = demander(client, reglages["modele"], e, rapport)
        except anthropic.APIError as erreur:
            rapport.anomalies.append(f"« {e['titre']} » : recherche impossible ({type(erreur).__name__})")
            continue
        rapport.cherchees += 1
        noms, source, adresses = lire_reponse(contenu)
        retenus = list(dict.fromkeys(connus[normaliser(n)] for n in noms if normaliser(n) in connus))
        inconnus = [n for n in noms if normaliser(n) not in connus]
        if retenus and not (source and any(_meme_page(source, a) for a in adresses)):
            rapport.anomalies.append(f"« {e['titre']} » : {', '.join(retenus)} sans page de résultat qui le confirme, "
                                     "pas retenu")
            retenus, inconnus = [], []
        db.noter_recherche(connexion, e, maintenant, retenus, inconnus, source if retenus else "")
        rapport.inconnus += [f"{n} (« {e['titre']} », {e['chaine']})" for n in inconnus]
        if retenus:
            rapport.trouvees.append((e["titre"], retenus))
            debut = datetime.fromisoformat(e["debut"]).astimezone(PARIS)
            db.noter_annonces(connexion, [{"id": f"web:{e['id']}", "titre": e["titre"],
                                           "jour": debut.date().isoformat(), "heure": f"{debut:%H:%M}",
                                           "invites": retenus, "url": source}], maintenant)
    return rapport
