"""Email du matin : la grille du jour triée par heure, puis les temps forts des 3 jours suivants.

Paramètres, tous en variables d'environnement (secrets GitHub une fois en ligne) :
SMTP_SERVEUR, SMTP_PORT (587 par défaut), SMTP_UTILISATEUR, SMTP_MOT_DE_PASSE,
EMAIL_EXPEDITEUR (SMTP_UTILISATEUR par défaut), EMAIL_DESTINATAIRE, ADRESSE_PAGE.
Le dépôt et les journaux GitHub sont publics : aucune adresse n'est jamais affichée.
"""

from __future__ import annotations

import html
import os
import smtplib
import ssl
from datetime import datetime, timedelta
from email.message import EmailMessage

from grille import affichage, db
from grille.config import Configuration
from grille.tv import PARIS

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]
PLATEFORMES = {"tv": "TV", "radio": "Radio", "youtube": "YouTube", "twitch": "Twitch", "web": "Web"}
SOURCES = {"tv": "Télévision", "radio": "Radio France", "youtube": "YouTube", "twitch": "Twitch",
           "annonces": "Invités annoncés (France Télévisions)"}
JOURS_TEMPS_FORTS = 3


class ConfigurationEmailIncomplete(Exception):
    pass


def _jour(d: datetime) -> str:
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]}"


def temps_fort(e: dict, candidats: set[str]) -> bool:
    """Débats, meetings, et toute émission où un candidat est annoncé."""
    return e["categorie"] in ("débat", "meeting") or any(nom in candidats for nom in e["invites"])


def contenu(connexion, config: Configuration, maintenant: datetime) -> dict:
    maintenant = maintenant.astimezone(PARIS)
    minuit = datetime.combine(maintenant.date(), datetime.min.time(), PARIS)
    candidats = {c["nom"] for c in config.candidats}
    aujourdhui = affichage.emissions(connexion, maintenant, minuit + timedelta(days=1))
    a_venir = [
        e for e in affichage.emissions(connexion, minuit + timedelta(days=1),
                                       minuit + timedelta(days=1 + JOURS_TEMPS_FORTS))
        if temps_fort(e, candidats) and datetime.fromisoformat(e["debut"]) >= minuit + timedelta(days=1)
    ]
    return {
        "titre_jour": _jour(maintenant),
        "aujourdhui": aujourdhui,
        "temps_forts": a_venir,
        "alertes": db.etat_des_sources(connexion, maintenant, SOURCES),
        "adresse_page": os.environ.get("ADRESSE_PAGE", ""),
    }


def diffuseurs(e: dict) -> str:
    """« LCP / Public Sénat (TV), BackSeat (Jean Massiet) (Twitch) » pour une émission fusionnée."""
    return ", ".join(f"{s['chaine']} ({PLATEFORMES[s['plateforme']]})" for s in e.get("sources") or [e])


def _ligne_texte(e: dict, avec_jour: bool = False) -> str:
    debut = datetime.fromisoformat(e["debut"])
    quand = (_jour(debut) + " " if avec_jour else "") + f"{debut:%H:%M}"
    invites = f" — avec {', '.join(e['invites'])}" if e["invites"] else ""
    lien = "".join(f"\n      {url}" for url in e["lien"])
    return f"  {quand}  {diffuseurs(e)} · {e['categorie']}\n    {e['titre']}{invites}{lien}"


def texte(c: dict) -> str:
    parties = [f"Grille politique — {c['titre_jour']}", ""]
    parties.append(f"AUJOURD'HUI ({len(c['aujourdhui'])})")
    parties += [_ligne_texte(e) for e in c["aujourdhui"]] or ["  Aucune émission politique annoncée."]
    parties += ["", f"TEMPS FORTS DES {JOURS_TEMPS_FORTS} PROCHAINS JOURS ({len(c['temps_forts'])})"]
    parties += [_ligne_texte(e, avec_jour=True) for e in c["temps_forts"]] or ["  Aucun débat ni meeting annoncé."]
    if c["alertes"]:
        parties += ["", "ÉTAT DES SOURCES"] + [f"  ! {a}" for a in c["alertes"]]
    if c["adresse_page"]:
        parties += ["", f"Grille complète : {c['adresse_page']}"]
    return "\n".join(parties) + "\n"


_COULEURS = {"débat": "#b3261e", "interview": "#1d5fa8", "meeting": "#a35400", "analyse": "#3d6b45"}


def _ligne_html(e: dict, avec_jour: bool = False) -> str:
    debut = datetime.fromisoformat(e["debut"])
    quand = (html.escape(_jour(debut)) + "<br>" if avec_jour else "") + f"<b>{debut:%H:%M}</b>"
    titre = html.escape(e["titre"])
    if e["lien"]:
        titre = f'<a href="{html.escape(e["lien"][0])}" style="color:#1f3a5f">{titre}</a>'
    invites = f'<div style="color:#5b6470;font-size:13px">Avec {html.escape(", ".join(e["invites"]))}</div>' if e["invites"] else ""
    # Émission fusionnée : un lien par autre diffuseur, sous le titre.
    autres = [f'<a href="{html.escape(src["lien"][0])}" style="color:#1f3a5f">{html.escape(src["chaine"])}'
              + (f' ({html.escape(src["precision"])})' if src.get("precision") else "") + "</a>"
              for src in (e.get("sources") or [])[1:] if src["lien"]]
    if autres:
        invites += f'<div style="font-size:13px">Aussi sur {" · ".join(autres)}</div>'
    couleur = _COULEURS.get(e["categorie"], "#5b6470")
    return (
        '<tr><td style="padding:8px 10px 8px 0;vertical-align:top;white-space:nowrap;font-size:14px">' + quand + "</td>"
        f'<td style="padding:8px 0;border-left:3px solid {couleur};padding-left:10px">'
        f'<div style="font-size:12px;color:#5b6470">{html.escape(diffuseurs(e))} · '
        f'<span style="color:{couleur};font-weight:bold;text-transform:uppercase">{html.escape(e["categorie"])}</span></div>'
        f'<div style="font-size:15px;font-weight:600">{titre}</div>{invites}</td></tr>'
    )


def page_html(c: dict) -> str:
    def section(titre: str, lignes: list[str], vide: str) -> str:
        corps = "".join(lignes) or f'<tr><td style="color:#5b6470;padding:8px 0">{vide}</td></tr>'
        return (f'<h2 style="font-size:15px;text-transform:uppercase;color:#5b6470;margin:24px 0 4px">{titre}</h2>'
                f'<table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse">{corps}</table>')

    morceaux = [
        '<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#1b1f24;max-width:640px">',
        f'<h1 style="font-size:20px;margin:0 0 4px">Grille politique — {html.escape(c["titre_jour"])}</h1>',
        section(f"Aujourd'hui ({len(c['aujourdhui'])})", [_ligne_html(e) for e in c["aujourdhui"]],
                "Aucune émission politique annoncée."),
        section(f"Temps forts des {JOURS_TEMPS_FORTS} prochains jours", [_ligne_html(e, True) for e in c["temps_forts"]],
                "Aucun débat ni meeting annoncé."),
    ]
    if c["alertes"]:
        morceaux.append('<h2 style="font-size:15px;text-transform:uppercase;color:#b3261e;margin:24px 0 4px">État des sources</h2><ul>'
                        + "".join(f"<li>{html.escape(a)}</li>" for a in c["alertes"]) + "</ul>")
    if c["adresse_page"]:
        morceaux.append(f'<p style="margin-top:24px"><a href="{html.escape(c["adresse_page"])}" '
                        'style="background:#1f3a5f;color:#fff;padding:10px 16px;border-radius:8px;text-decoration:none">'
                        "Ouvrir la grille complète</a></p>")
    morceaux.append("</div>")
    return "".join(morceaux)


def message(c: dict) -> EmailMessage:
    m = EmailMessage()
    nb = len(c["aujourdhui"])
    m["Subject"] = f"Grille politique — {c['titre_jour']} : {nb} émission{'s' if nb > 1 else ''}"
    m.set_content(texte(c))
    m.add_alternative(page_html(c), subtype="html")
    return m


def envoyer(m: EmailMessage) -> None:
    env = os.environ
    manquants = [v for v in ("SMTP_SERVEUR", "SMTP_UTILISATEUR", "SMTP_MOT_DE_PASSE", "EMAIL_DESTINATAIRE") if not env.get(v)]
    if manquants:
        raise ConfigurationEmailIncomplete("secrets absents : " + ", ".join(manquants))
    m["From"] = env.get("EMAIL_EXPEDITEUR") or env["SMTP_UTILISATEUR"]
    m["To"] = env["EMAIL_DESTINATAIRE"]
    port = int(env.get("SMTP_PORT") or 587)
    contexte = ssl.create_default_context()
    if port == 465:
        serveur = smtplib.SMTP_SSL(env["SMTP_SERVEUR"], port, context=contexte, timeout=60)
    else:
        serveur = smtplib.SMTP(env["SMTP_SERVEUR"], port, timeout=60)
        serveur.starttls(context=contexte)
    with serveur:
        serveur.login(env["SMTP_UTILISATEUR"], env["SMTP_MOT_DE_PASSE"])
        serveur.send_message(m)


def attente_avant_7h(maintenant: datetime) -> float | None:
    """Secondes à attendre avant 7 h (heure de Paris), ou None si l'heure ne convient pas.

    GitHub déclenche ses tâches en heure UTC, avec du retard : la tâche est lancée
    deux fois (6 h 30 en heure d'été comme en heure d'hiver) et attend 7 h.
    Avant 6 h, c'est le déclenchement prévu pour l'autre saison : on ne fait rien.
    Après 10 h, un email du matin n'a plus de sens.
    """
    maintenant = maintenant.astimezone(PARIS)
    sept_heures = maintenant.replace(hour=7, minute=0, second=0, microsecond=0)
    if maintenant.hour < 6 or maintenant.hour >= 10:
        return None
    return max(0.0, (sept_heures - maintenant).total_seconds())
