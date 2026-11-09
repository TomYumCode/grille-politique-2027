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
from grille.campagne import Campagne
from grille.config import Configuration
from grille.filtre import normaliser
from grille.tv import PARIS

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]
PLATEFORMES = {"tv": "TV", "radio": "Radio", "youtube": "YouTube", "twitch": "Twitch", "web": "Agenda"}
SOURCES = {"tv": "Télévision", "radio": "Radios", "youtube": "YouTube", "twitch": "Twitch",
           "web": "Agendas des partis", "annonces": "Invités annoncés (France Télévisions)",
           "directs": "Sujet du jour des émissions en cours (france.tv)",
           "invites": "Invités cherchés sur le web (Claude)", "rss": "Flux RSS (mesure)"}
JOURS_TEMPS_FORTS = 3
EXEMPLES_DOUTEUX = 10
NOMS_SOURCES = {"tv": "télévision", "radio": "radio", "youtube": "YouTube", "twitch": "Twitch"}


class ConfigurationEmailIncomplete(Exception):
    pass


def _jour(d: datetime) -> str:
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]}"


def temps_fort(e: dict, personnes: set[str]) -> bool:
    """Émission où un candidat officiel (déclaré ou désigné) ou un membre de son équipe de
    campagne est présent : interview, débat, meeting. Les mots-clés seuls ne suffisent pas
    (n'importe quelle émission peut en contenir)."""
    return any(nom in personnes for nom in e["invites"])


def mesure_douteux(connexion, maintenant: datetime) -> dict:
    """Cas douteux vus pour la première fois ces dernières 24 h : nombre, répartition, exemples à venir."""
    cas = db.douteux_depuis(connexion, maintenant - timedelta(hours=24))
    par_source: dict[str, int] = {}
    for c in cas:
        par_source[c["source"]] = par_source.get(c["source"], 0) + 1
    a_venir = [c for c in cas if datetime.fromisoformat(c["debut"]) >= maintenant]
    # Exemples variés : un motif différent d'abord, puis le reste.
    exemples, motifs = [], set()
    for c in a_venir:
        if c["motif"] not in motifs:
            exemples.append(c)
            motifs.add(c["motif"])
    exemples += [c for c in a_venir if c not in exemples]
    return {"nombre": len(cas), "par_source": par_source,
            "exemples": sorted(exemples[:EXEMPLES_DOUTEUX], key=lambda c: c["debut"])}


EXEMPLES_RSS = 10


def mesure_rss(connexion, maintenant: datetime) -> dict:
    """Annonces de passages médias repérées dans les flux RSS ces dernières 24 h : combien, combien
    la grille ignorait encore, par quels flux, avec des exemples (d'abord celles qu'elle ignorait)."""
    annonces = db.rss_depuis(connexion, maintenant - timedelta(hours=24))
    par_flux: dict[str, int] = {}
    for a in annonces:
        par_flux[a["flux"]] = par_flux.get(a["flux"], 0) + 1
    nouvelles = [a for a in annonces if not a["deja_en_grille"]]
    exemples = (nouvelles + [a for a in annonces if a["deja_en_grille"]])[:EXEMPLES_RSS]
    return {"nombre": len(annonces), "inconnues": len(nouvelles),
            "par_flux": sorted(par_flux.items(), key=lambda x: -x[1]), "exemples": exemples}


ARTICLES_MIN_CANDIDAT = 2  # un seul article ne suffit pas (rumeur, citation)


def candidats_possibles(connexion, config: Configuration, maintenant: datetime) -> list[dict]:
    """Personnes présentées comme candidates par au moins deux articles RSS ces 7 derniers jours,
    toujours absentes de politique.yaml : nom, articles, ligne à copier dans la liste."""
    from grille.rss import noms_connus  # évite une importation circulaire

    connus = noms_connus(config)
    resultat = []
    for nom, articles in db.rss_candidats_depuis(connexion, maintenant - timedelta(days=7)).items():
        if normaliser(nom) in connus or len(articles) < ARTICLES_MIN_CANDIDAT:
            continue
        famille = nom.split()[-1]
        jour = datetime.fromisoformat(articles[0]["vu_le"])
        ligne = (f'  - {{nom: "{nom}", alias: ["{famille}"], parti: "", sigle: "", '
                 f'statut: "à vérifier (vu le {jour.day} {MOIS[jour.month - 1]} {jour.year})"}}')
        resultat.append({"nom": nom, "articles": articles, "flux": sorted({a["flux"] for a in articles}),
                         "ligne": ligne})
    return sorted(resultat, key=lambda c: -len(c["articles"]))


def _annonces(n: int) -> str:
    return f"{n} annonce" + ("s" if n > 1 else "")


def _heure_rss(a: dict) -> str:
    vu = datetime.fromisoformat(a["vu_le"])
    publie = f"publié {datetime.fromisoformat(a['publie']):%H:%M}, " if a["publie"] else ""
    return f"{publie}vu {_jour(vu)} {vu:%H:%M}"


def _repartition(d: dict) -> str:
    return ", ".join(f"{n} {NOMS_SOURCES.get(s, s)}" for s, n in sorted(d["par_source"].items(), key=lambda x: -x[1]))


def contenu(connexion, config: Configuration, maintenant: datetime) -> dict:
    maintenant = maintenant.astimezone(PARIS)
    minuit = datetime.combine(maintenant.date(), datetime.min.time(), PARIS)
    candidats = config.candidats_officiels() | config.equipes_de_campagne()
    aujourdhui = affichage.emissions(connexion, maintenant, minuit + timedelta(days=1))
    a_venir = [
        e for e in affichage.emissions(connexion, minuit + timedelta(days=1),
                                       minuit + timedelta(days=1 + JOURS_TEMPS_FORTS))
        if temps_fort(e, candidats) and datetime.fromisoformat(e["debut"]) >= minuit + timedelta(days=1)
    ]
    classer = Campagne(config).motif

    def nommer(e: dict) -> dict:
        return dict(e, invites_affiches=config.nommer(e["invites"]), cites_affiches=config.nommer(e.get("cites") or []),
                    presentation=affichage.presentation(e))

    return {
        "titre_jour": _jour(maintenant),
        "aujourdhui": [nommer(e) for e in aujourdhui],
        # Aujourd'hui, en deux parties : la campagne d'abord, puis le reste de la politique.
        "presidentielle": [nommer(e) for e in aujourdhui if classer(e)],
        "autres": [nommer(e) for e in aujourdhui if not classer(e)],
        "temps_forts": [nommer(e) for e in a_venir],
        "alertes": db.etat_des_sources(connexion, maintenant, SOURCES),
        "douteux": mesure_douteux(connexion, maintenant),
        "rss": mesure_rss(connexion, maintenant),
        "candidats_possibles": candidats_possibles(connexion, config, maintenant),
        "adresse_page": os.environ.get("ADRESSE_PAGE", ""),
    }


def diffuseurs(e: dict) -> str:
    """« LCP / Public Sénat (TV), BackSeat (Jean Massiet) (Twitch) » pour une émission fusionnée."""
    return ", ".join(f"{s['chaine']} ({PLATEFORMES[s['plateforme']]})" for s in e.get("sources") or [e])


def _ligne_texte(e: dict, avec_jour: bool = False) -> str:
    debut = datetime.fromisoformat(e["debut"])
    quand = (_jour(debut) + " " if avec_jour else "") + f"{debut:%H:%M}"
    presents, cites = e.get("invites_affiches", e["invites"]), e.get("cites_affiches", e.get("cites") or [])
    invites = f" — avec {', '.join(presents)}" if presents else ""
    if e.get("presentation"):
        invites += f" — {e['presentation']}"
    if cites:
        invites += f" — à propos de {', '.join(cites)}"
    lien = "".join(f"\n      {url}" for url in e["lien"])
    return f"  {quand}  {diffuseurs(e)} · {e['categorie']}\n    {e['titre']}{invites}{lien}"


def texte(c: dict) -> str:
    parties = [f"Grille politique — {c['titre_jour']}", ""]
    parties.append(f"PRÉSIDENTIELLE 2027 — AUJOURD'HUI ({len(c['presidentielle'])})")
    parties += [_ligne_texte(e) for e in c["presidentielle"]] or ["  Aucune émission sur la présidentielle annoncée."]
    parties += ["", f"TOUTE LA POLITIQUE — AUTRES ÉMISSIONS DU JOUR ({len(c['autres'])})"]
    parties += [_ligne_texte(e) for e in c["autres"]] or ["  Aucune autre émission politique annoncée."]
    parties += ["", f"TEMPS FORTS DE LA PRÉSIDENTIELLE — {JOURS_TEMPS_FORTS} PROCHAINS JOURS ({len(c['temps_forts'])})"]
    parties += [_ligne_texte(e, avec_jour=True) for e in c["temps_forts"]] or ["  Aucun candidat ni membre d'équipe de campagne annoncé."]
    d = c.get("douteux")
    if d and d["nombre"]:
        parties += ["", f"MESURE — CAS DOUTEUX DES DERNIÈRES 24 H : {d['nombre']} ({_repartition(d)})",
                    "  Émissions écartées qui pourraient être politiques : Claude les jugerait si le classement",
                    "  par modèle était activé. Exemples :"]
        parties += [f"  {_jour(datetime.fromisoformat(x['debut']))} {x['debut'][11:16]}  {x['chaine']} — {x['titre']}"
                    f"  ({x['motif']})" for x in d["exemples"]]
    candidats_possibles = c.get("candidats_possibles") or []
    if candidats_possibles:
        parties += ["", "CANDIDATS POSSIBLES À AJOUTER (articles de presse des 7 derniers jours)",
                    "  Absents de config/politique.yaml. À vérifier avant d'ajouter la ligne proposée :"]
    for cand in candidats_possibles:
        parties += [f"  {cand['nom']} : {len(cand['articles'])} articles ({', '.join(cand['flux'])})"]
        parties += [f"    {a['titre']}  {a['lien']}" for a in cand["articles"][:3]]
        parties += [f"    Ligne à copier : {cand['ligne'].strip()}"]
    r = c.get("rss")
    if r and r["nombre"]:
        parties += ["", f"MESURE — FLUX RSS DES DERNIÈRES 24 H : {_annonces(r['nombre'])} de passages médias, "
                        f"dont {r['inconnues']} que la grille ignorait",
                    "  " + ", ".join(f"{n} {f}" for f, n in r["par_flux"]) + ". Exemples :"]
        parties += [f"  {'NOUVEAU ' if not a['deja_en_grille'] else ''}{a['titre']} ({a['flux']} ; "
                    f"{', '.join(a['personnes'])} ; {', '.join(a['chaines'])} ; {_heure_rss(a)})  {a['lien']}"
                    for a in r["exemples"]]
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
    presents, cites = e.get("invites_affiches", e["invites"]), e.get("cites_affiches", e.get("cites") or [])
    invites = f'<div style="color:#5b6470;font-size:13px">Avec {html.escape(", ".join(presents))}</div>' if presents else ""
    if e.get("presentation"):
        invites += f'<div style="color:#5b6470;font-size:13px">{html.escape(e["presentation"])}</div>'
    if cites:
        invites += ('<div style="color:#5b6470;font-size:13px;font-style:italic">À propos de '
                    f'{html.escape(", ".join(cites))}</div>')
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
        section(f"Présidentielle 2027 — aujourd'hui ({len(c['presidentielle'])})",
                [_ligne_html(e) for e in c["presidentielle"]], "Aucune émission sur la présidentielle annoncée."),
        section(f"Toute la politique — autres émissions du jour ({len(c['autres'])})",
                [_ligne_html(e) for e in c["autres"]], "Aucune autre émission politique annoncée."),
        section(f"Temps forts de la présidentielle — {JOURS_TEMPS_FORTS} prochains jours",
                [_ligne_html(e, True) for e in c["temps_forts"]], "Aucun candidat ni membre d'équipe de campagne annoncé."),
    ]
    d = c.get("douteux")
    if d and d["nombre"]:
        morceaux.append(
            '<h2 style="font-size:15px;text-transform:uppercase;color:#5b6470;margin:24px 0 4px">'
            f'Mesure — cas douteux des dernières 24 h : {d["nombre"]}</h2>'
            f'<p style="font-size:13px;color:#5b6470;margin:0 0 6px">{html.escape(_repartition(d))}. '
            "Émissions écartées qui pourraient être politiques : Claude les jugerait si le classement par modèle "
            "était activé. Exemples :</p><ul style=\"font-size:13px;padding-left:18px\">"
            + "".join(f"<li>{html.escape(_jour(datetime.fromisoformat(x['debut'])))} {x['debut'][11:16]} · "
                      f"{html.escape(x['chaine'])} — <b>{html.escape(x['titre'])}</b> "
                      f"<span style=\"color:#5b6470\">({html.escape(x['motif'])})</span></li>" for x in d["exemples"])
            + "</ul>")
    if c.get("candidats_possibles"):
        morceaux.append(
            '<h2 style="font-size:15px;text-transform:uppercase;color:#1f3a5f;margin:24px 0 4px">'
            "Candidats possibles à ajouter</h2>"
            '<p style="font-size:13px;color:#5b6470;margin:0 0 6px">Présentés comme candidats par plusieurs articles '
            "ces 7 derniers jours, absents de config/politique.yaml. À vérifier avant d'ajouter la ligne proposée.</p>"
            '<ul style="font-size:13px;padding-left:18px">'
            + "".join(f"<li><b>{html.escape(cand['nom'])}</b> : {len(cand['articles'])} articles "
                      f"({html.escape(', '.join(cand['flux']))})<ul>"
                      + "".join(f"<li><a href=\"{html.escape(a['lien'])}\">{html.escape(a['titre'])}</a></li>"
                                for a in cand["articles"][:3])
                      + f"</ul><code style=\"font-size:12px\">{html.escape(cand['ligne'].strip())}</code></li>"
                      for cand in c["candidats_possibles"])
            + "</ul>")
    r = c.get("rss")
    if r and r["nombre"]:
        morceaux.append(
            '<h2 style="font-size:15px;text-transform:uppercase;color:#5b6470;margin:24px 0 4px">'
            f'Mesure — flux RSS des dernières 24 h : {_annonces(r["nombre"])}, dont {r["inconnues"]} que la grille '
            "ignorait</h2>"
            f'<p style="font-size:13px;color:#5b6470;margin:0 0 6px">'
            f'{html.escape(", ".join(f"{n} {f}" for f, n in r["par_flux"]))}. Rien n\'est ajouté à la grille '
            "pendant la mesure. Exemples :</p><ul style=\"font-size:13px;padding-left:18px\">"
            + "".join(f"<li>{'<b>Nouveau</b> · ' if not a['deja_en_grille'] else ''}"
                      f"<a href=\"{html.escape(a['lien'])}\">{html.escape(a['titre'])}</a> "
                      f"<span style=\"color:#5b6470\">({html.escape(a['flux'])} ; "
                      f"{html.escape(', '.join(a['personnes']))} ; {html.escape(', '.join(a['chaines']))} ; "
                      f"{html.escape(_heure_rss(a))})</span></li>" for a in r["exemples"])
            + "</ul>")
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
    nb, p = len(c["aujourdhui"]), len(c["presidentielle"])
    m["Subject"] = (f"Grille politique — {c['titre_jour']} : {p} sur la présidentielle, "
                    f"{nb} émission{'s' if nb > 1 else ''} en tout")
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
    Après 7 h, l'email part tout de suite : GitHub saute parfois tous les déclenchements
    du matin (le 17 octobre 2026, le premier est venu à 10 h 21), et un email en retard
    vaut mieux que pas d'email.
    """
    maintenant = maintenant.astimezone(PARIS)
    sept_heures = maintenant.replace(hour=7, minute=0, second=0, microsecond=0)
    if maintenant.hour < 6:
        return None
    return max(0.0, (sept_heures - maintenant).total_seconds())
