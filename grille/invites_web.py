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

Grandes émissions à surveiller (`a_surveiller:` de config/recherche.yaml, par exemple les
journaux de 20 h de TF1 et France 2) : absentes de la grille, elles reçoivent parfois un
responsable politique (Marine Tondelier au 20 h de TF1, 9 novembre 2026, annoncée à 15 h 50).
Claude vérifie deux fois par jour s'il y a un invité politique : à l'heure des annonces
(`heure_annonces`, 17 h) puis juste avant l'émission. L'émission n'entre dans la grille
(identifiant « recherche:… », jamais annulé par les autres sources) que si un invité de
politique.yaml est confirmé par une page des résultats.
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
from grille.tv import PARIS, statut

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


SURVEILLANCE = """\
Cette émission n'est pas une émission politique : la plupart des jours, elle ne reçoit aucun \
responsable politique. On cherche seulement si un responsable politique (candidat, élu, \
ministre, dirigeant de parti) y est invité en plateau ou en interview pour cette diffusion. Les \
personnes qui apparaissent seulement dans un reportage ne comptent pas."""


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


def question(e: dict, surveillee: bool = False) -> str:
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
    if surveillee:
        lignes.append(SURVEILLANCE)
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


def demander(client, modele: str, e: dict, rapport: Rapport, surveillee: bool = False) -> list[dict]:
    """Pose la question ; renvoie les blocs de la réponse finale (dictionnaires)."""
    messages = [{"role": "user", "content": question(e, surveillee)}]
    for _ in range(REPRISES + 1):
        # Refus d'un filtre de sécurité : la même question passe à un autre modèle (Opus, Sonnet ;
        # Haiku n'a pas de modèle de repli).
        repli = ({"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
                 if re.match(r"claude-(opus|sonnet|fable)-", modele) else {})
        reponse = client.beta.messages.create(
            model=modele,
            max_tokens=8000,
            **repli,
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


def emissions_surveillees(config: Configuration, maintenant: datetime) -> list[dict]:
    """Diffusions du jour des grandes émissions à surveiller, au format d'une émission de la grille."""
    jour = maintenant.astimezone(PARIS).date()
    resultat = []
    chaines = {c.nom: c for c in config.chaines}
    for s in config.recherche.get("a_surveiller") or []:
        chaine = chaines.get(s["chaine"])
        h, m = map(int, s["heure"].split(":"))
        debut = datetime(jour.year, jour.month, jour.day, h, m, tzinfo=PARIS)
        fin = debut + timedelta(minutes=int(s.get("duree") or 45))
        resultat.append({
            "id": f"recherche:{normaliser(s['chaine']).replace(' ', '-')}:{debut:%Y%m%d%H%M}",
            "titre": s["titre"], "debut": debut.isoformat(timespec="seconds"),
            "fin": fin.isoformat(timespec="seconds"), "plateforme": chaine.plateforme if chaine else "tv",
            "chaine": s["chaine"], "categorie": "interview", "invites": [], "cites": [], "resume": "",
            "lien": list(chaine.direct) if chaine else [], "statut": statut(debut, fin, maintenant),
            "filtre": LISTE_BLANCHE, "nature": "",
        })
    return resultat


def surveillance_due(e: dict, config: Configuration, connexion, maintenant: datetime) -> bool:
    """Premier essai à l'heure des annonces ; second juste avant l'émission, si rien trouvé."""
    debut = datetime.fromisoformat(e["debut"])
    reglages = config.recherche
    h, m = map(int, reglages.get("heure_annonces", "17:00").split(":"))
    annonces = min(debut.replace(hour=h, minute=m), debut - timedelta(minutes=reglages["avant_debut"]))
    juste_avant = debut - timedelta(minutes=reglages["avant_debut"])
    if not annonces <= maintenant <= debut + timedelta(minutes=reglages["apres_debut"]):
        return False
    deja = db.recherche_invites(connexion, e["id"])
    if deja is None:
        return True
    return (deja["essais"] < ESSAIS_MAX and not deja["invites"] and maintenant >= juste_avant
            and deja["derniere"] < juste_avant)


def _verifier(contenu: list[dict], connus: dict[str, str]) -> tuple[list[str], list[str], str, bool]:
    """(noms retenus, noms inconnus, source, source confirmée par les résultats)."""
    noms, source, adresses = lire_reponse(contenu)
    retenus = list(dict.fromkeys(connus[normaliser(n)] for n in noms if normaliser(n) in connus))
    inconnus = [n for n in noms if normaliser(n) not in connus]
    confirmee = bool(source) and any(_meme_page(source, a) for a in adresses)
    return retenus, inconnus, source, confirmee


def collecter(config: Configuration, connexion, maintenant: datetime, client=None) -> Rapport:
    rapport = Rapport()
    reglages = config.recherche
    if not reglages.get("actif"):
        rapport.interrompu = "recherche arrêtée (config/recherche.yaml)"
        return rapport
    maintenant = maintenant.astimezone(PARIS)
    candidates = [(e, False) for e in affichage.emissions(connexion, maintenant - timedelta(hours=2),
                                                           maintenant + timedelta(hours=1))
                  if a_chercher(e, config, connexion, maintenant)]
    candidates += [(e, True) for e in emissions_surveillees(config, maintenant)
                   if surveillance_due(e, config, connexion, maintenant)]
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
    for e, surveillee in candidates:
        if db.recherches_du_jour(connexion, maintenant) >= reglages["recherches_par_jour"]:
            rapport.plafond_atteint = True
            break
        try:
            contenu = demander(client, reglages["modele"], e, rapport, surveillee)
        except anthropic.APIError as erreur:
            rapport.anomalies.append(f"« {e['titre']} » : recherche impossible ({type(erreur).__name__})")
            continue
        rapport.cherchees += 1
        retenus, inconnus, source, confirmee = _verifier(contenu, connus)
        if retenus and not confirmee:
            rapport.anomalies.append(f"« {e['titre']} » : {', '.join(retenus)} sans page de résultat qui le confirme, "
                                     "pas retenu")
            retenus, inconnus = [], []
        db.noter_recherche(connexion, e, maintenant, retenus, inconnus, source if retenus else "")
        rapport.inconnus += [f"{n} (« {e['titre']} », {e['chaine']})" for n in inconnus]
        if retenus and surveillee:
            # Grande émission : elle entre dans la grille avec son invité.
            rapport.trouvees.append((f"{e['titre']} ({e['chaine']})", retenus))
            ligne = dict(e, titre=f"{e['titre']} — {', '.join(retenus)}", invites=retenus,
                         resume=f"Invité trouvé sur le web : {source}")
            db.enregistrer_collecte(connexion, [ligne], ligne["plateforme"], set(), maintenant)
        elif retenus:
            rapport.trouvees.append((e["titre"], retenus))
            debut = datetime.fromisoformat(e["debut"]).astimezone(PARIS)
            db.noter_annonces(connexion, [{"id": f"web:{e['id']}", "titre": e["titre"],
                                           "jour": debut.date().isoformat(), "heure": f"{debut:%H:%M}",
                                           "invites": retenus, "url": source}], maintenant)
    return rapport


# Prix publics (dollars par million de jetons) et recherche web (10 $ les 1 000), pour estimer
# le coût d'un essai ; à vérifier sur la page des prix d'Anthropic avant de décider.
PRIX = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}
PRIX_RECHERCHE = 0.01


def cout(modele: str, jetons: dict) -> float | None:
    if modele not in PRIX:
        return None
    entree, sortie = PRIX[modele]
    return (jetons["entree"] * entree + jetons["sortie"] * sortie) / 1e6 + jetons["recherches"] * PRIX_RECHERCHE


def comparer(config: Configuration, client, modeles: list[str], essais: list[dict]) -> list[dict]:
    """Pose chaque question d'essai à chaque modèle ; rien n'est écrit en base."""
    connus = _noms_connus(config)
    resultats = []
    for essai in essais:
        e = {"id": "essai", "titre": essai["titre"], "chaine": essai["chaine"], "plateforme": essai["plateforme"],
             "debut": essai["debut"], "fin": essai.get("fin"), "resume": essai.get("resume", "")}
        for modele in modeles:
            rapport = Rapport()
            erreur = ""
            try:
                contenu = demander(client, modele, e, rapport, bool(essai.get("surveillee")))
            except Exception as ex:  # un modèle en panne n'arrête pas la comparaison
                contenu, erreur = [], type(ex).__name__
            retenus, inconnus, source, confirmee = _verifier(contenu, connus)
            attendu = essai.get("attendu")
            juste = None if attendu is None else sorted(retenus if confirmee else []) == sorted(attendu)
            resultats.append({"essai": f"{essai['titre']} ({essai['chaine']}, {essai['debut'][:10]})",
                              "modele": modele, "trouves": retenus, "inconnus": inconnus, "source": source,
                              "confirmee": confirmee, "juste": juste, "erreur": erreur,
                              "jetons": rapport.jetons, "cout": cout(modele, rapport.jetons)})
    return resultats
