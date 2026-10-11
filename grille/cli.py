"""Commandes : python -m grille init | verifier-acces | collecter[-tv|-radio|-youtube|-twitch] | lister | page | apercu
| chercher-tv | courriel | attente-7h."""

from __future__ import annotations

import argparse
import os
import smtplib
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import requests

from grille import acces, affichage, agendas, annonces, config, courriel, db, page, radio, tv, twitch, youtube

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]


def _charger_config(dossier: Path) -> config.Configuration | None:
    try:
        conf = config.charger(dossier)
    except config.ErreurConfig as e:
        print(f"ERREUR de configuration : {e}")
        return None
    par_plateforme = Counter(c.plateforme for c in conf.chaines)
    print(
        f"Configuration lue : {len(conf.chaines)} chaînes ("
        + ", ".join(f"{n} {p}" for p, n in sorted(par_plateforme.items()))
        + f"), dont {sum(c.a_confirmer for c in conf.chaines)} à confirmer"
    )
    print(
        f"  {len(conf.candidats)} candidats, {len(conf.partis)} partis, "
        f"{len(conf.mots_cles)} mots-clés (+ {len(conf.mots_cles_titre)} dans le titre seulement), {len(conf.liste_blanche.get('emissions') or [])} émissions en liste blanche"
    )
    for anomalie in conf.anomalies:
        print(f"  ATTENTION {anomalie}")
    return conf


def cmd_init(args: argparse.Namespace) -> int:
    conf = _charger_config(args.config)
    connexion = db.ouvrir(args.base)
    nb = connexion.execute("SELECT COUNT(*) FROM emissions").fetchone()[0]
    connexion.close()
    print(f"Base prête : {args.base} (table emissions, {nb} émission(s))")
    return 0 if conf is not None else 1


def cmd_verifier_acces(args: argparse.Namespace) -> int:
    conf = _charger_config(args.config)
    if conf is None:
        return 1
    resultats = acces.verifier_tout(conf)
    for r in resultats:
        print(f"[{r.etat:^13}] {r.source} : {r.detail}")
    return 1 if any(r.etat == "erreur" for r in resultats) else 0


def afficher_grille(emissions: list[dict]) -> None:
    jour_courant = None
    for e in emissions:
        debut = datetime.fromisoformat(e["debut"])
        if debut.date() != jour_courant:
            jour_courant = debut.date()
            print(f"\n{JOURS[debut.weekday()].capitalize()} {debut.day} {MOIS[debut.month - 1]}")
        invites = f" — avec {', '.join(e['invites'])}" if e["invites"] else ""
        etat = f" [{e['statut']}]" if e["statut"] != "annoncé" else ""
        plateforme = courriel.PLATEFORMES[e["plateforme"]]
        aussi = f"  [aussi : {', '.join(s['chaine'] for s in e['sources'][1:])}]" if e.get("sources") else ""
        print(f"  {debut:%H:%M}  {plateforme:<7} {e['chaine'][:24]:<24} {e['categorie']:<9} "
              f"{e['titre']}{invites}{etat}  ({e['filtre']}){aussi}")


def _horizon() -> tuple[datetime, datetime]:
    maintenant = datetime.now(tv.PARIS)
    fin = datetime.combine(maintenant.date() + timedelta(days=tv.JOURS_AFFICHES), datetime.min.time(), tv.PARIS)
    return maintenant, fin


def _resume(retenues: list[dict]) -> str:
    par_filtre = Counter(e["filtre"] for e in retenues)
    return f"{len(retenues)} retenues ({', '.join(f'{n} {f}' for f, n in sorted(par_filtre.items())) or 'aucune'})"


def _motifs(retenues: list[dict]) -> None:
    for e in retenues:
        print(f"  {e['debut'][:16]}  {e['chaine'][:20]:<20} {e['titre'][:60]:<60} ← {e['filtre']} : {e['motif']}")


def _a_confirmer(resultats: dict[str, bool]) -> None:
    for nom, trouvee in sorted(resultats.items()):
        verdict = "trouvée, on peut retirer « a_confirmer »" if trouvee else "INTROUVABLE, adresse à corriger"
        print(f"  Chaîne à confirmer — {nom} : {verdict}")


def _etape_tv(conf, connexion, maintenant, args) -> bool:
    fichier = getattr(args, "fichier", None)
    if fichier:
        chemin = fichier
        print(f"Télévision : guide lu depuis {chemin}")
    else:
        print(f"Télévision : téléchargement du guide {acces.XMLTV_TNT}")
        try:
            chemin = tv.telecharger(requests.Session())
        except requests.RequestException as e:
            print(f"  ERREUR guide télévision inaccessible ({e})")
            db.noter_collecte(connexion, "tv", maintenant, False, 0, [], f"guide inaccessible ({e})")
            return False
    try:
        rapport = tv.collecter(conf, chemin, connexion, maintenant)
    finally:
        if not fichier:
            chemin.unlink(missing_ok=True)
    print(
        f"  {rapport.lus} programmes lus sur les chaînes configurées, {rapport.dans_l_horizon} à venir "
        f"(dont {rapport.masques} de nuit ignorés) ; "
        f"{_resume(rapport.retenues)}, {rapport.annulees} passées en « annulé »"
    )
    for nom in rapport.chaines_absentes:
        print(f"  ATTENTION chaîne absente du guide : {nom}")
    reussie = rapport.lus > 0
    db.noter_collecte(connexion, "tv", maintenant, reussie, len(rapport.retenues),
                      [f"chaîne absente du guide : {n}" for n in rapport.chaines_absentes],
                      "" if reussie else "guide vide pour les chaînes configurées")
    if args.motifs:
        _motifs(rapport.retenues)
    return reussie


def _etape_radio(conf, connexion, maintenant, args) -> bool:
    print("Radio France :")
    rapport = radio.collecter(conf, requests.Session(), connexion, maintenant)
    if rapport.interrompu == radio.SANS_CLE:
        # Clé demandée mais pas encore reçue : une ligne de rappel dans l'email, pas une panne.
        print(f"  en attente : {rapport.interrompu}")
        db.noter_collecte(connexion, "radio", maintenant, True, 0, ["clé Radio France pas encore en place"])
        return True
    db.noter_collecte(connexion, "radio", maintenant, not rapport.interrompu, len(rapport.retenues),
                      rapport.anomalies, rapport.interrompu)
    if rapport.interrompu:
        print(f"  ERREUR {rapport.interrompu}")
        return False
    print(
        f"  {rapport.stations_lues} stations lues, {rapport.programmes} programmes à venir "
        f"(dont {rapport.masques} de nuit ignorés) ; "
        f"{_resume(rapport.retenues)}, {rapport.annulees} passées en « annulé »"
    )
    for anomalie in rapport.anomalies:
        print(f"  ATTENTION {anomalie}")
    if args.motifs:
        _motifs(rapport.retenues)
    return True


def _etape_annonces(conf, connexion, maintenant, args) -> bool:
    print("Invités annoncés (communiqués de France Télévisions) :")
    rapport = annonces.collecter(conf, requests.Session(), connexion, maintenant)
    db.noter_collecte(connexion, "annonces", maintenant, not rapport.interrompu, len(rapport.retenues),
                      rapport.anomalies, rapport.interrompu)
    if rapport.interrompu:
        print(f"  ERREUR {rapport.interrompu}")
        return False
    print(f"  {rapport.pages_lues} pages lues, {rapport.cartes} communiqués, {len(rapport.retenues)} annonces d'invités à venir")
    for anomalie in rapport.anomalies:
        print(f"  ATTENTION {anomalie}")
    for a in rapport.retenues:
        print(f"  {a.jour} {a.heure or '--:--'}  {a.titre[:60]:<60} → {', '.join(a.invites)}")
    return True


def _etape_agendas(conf, connexion, maintenant, args) -> bool:
    print("Agendas des partis et des candidats :")
    rapport = agendas.collecter(conf, requests.Session(), connexion, maintenant)
    db.noter_collecte(connexion, "web", maintenant, not rapport.interrompu, len(rapport.retenues),
                      rapport.anomalies, rapport.interrompu)
    if rapport.interrompu:
        print(f"  ERREUR {rapport.interrompu}")
        return False
    print(f"  {rapport.agendas_lus} agendas lus, {rapport.rendez_vous} rendez-vous à venir ; "
          f"{_resume(rapport.retenues)}, {rapport.annulees} passés en « annulé »")
    for anomalie in rapport.anomalies:
        print(f"  ATTENTION {anomalie}")
    if args.motifs:
        _motifs(rapport.retenues)
    return True


def _etape_youtube(conf, connexion, maintenant, args) -> bool:
    print("YouTube :")
    rapport = youtube.collecter(conf, requests.Session(), connexion, maintenant)
    db.noter_collecte(connexion, "youtube", maintenant, not rapport.interrompu, len(rapport.retenues),
                      rapport.anomalies, rapport.interrompu)
    if rapport.interrompu and not rapport.unites:
        print(f"  ERREUR {rapport.interrompu}")
        return False
    print(
        f"  {rapport.chaines_lues} chaînes lues, {rapport.videos_examinees} vidéos examinées ; "
        f"{_resume(rapport.retenues)}, {rapport.annulees} passées en « annulé » ; quota consommé : {rapport.unites} unités"
    )
    if rapport.interrompu:
        print(f"  ERREUR collecte interrompue : {rapport.interrompu}")
    for anomalie in rapport.anomalies:
        print(f"  ATTENTION {anomalie}")
    _a_confirmer(rapport.a_confirmer)
    if args.motifs:
        _motifs(rapport.retenues)
    return not rapport.interrompu


def _etape_twitch(conf, connexion, maintenant, args) -> bool:
    print("Twitch :")
    rapport = twitch.collecter(conf, requests.Session(), connexion, maintenant)
    db.noter_collecte(connexion, "twitch", maintenant, not rapport.interrompu, len(rapport.retenues),
                      rapport.anomalies, rapport.interrompu)
    if rapport.interrompu and not rapport.chaines_lues:
        print(f"  ERREUR {rapport.interrompu}")
        return False
    print(
        f"  {rapport.chaines_lues} chaînes lues, {rapport.en_direct} en direct, {rapport.creneaux} créneaux à venir ; "
        f"{_resume(rapport.retenues)}, {rapport.annulees} passées en « annulé », {rapport.directs_finis} directs terminés"
    )
    if rapport.interrompu:
        print(f"  ERREUR collecte interrompue : {rapport.interrompu}")
    for anomalie in rapport.anomalies:
        print(f"  ATTENTION {anomalie}")
    _a_confirmer(rapport.a_confirmer)
    if args.motifs:
        _motifs(rapport.retenues)
    return not rapport.interrompu


ETAPES = {"tv": _etape_tv, "radio": _etape_radio, "youtube": _etape_youtube, "twitch": _etape_twitch,
          "annonces": _etape_annonces, "web": _etape_agendas}
NOMS = {"tv": "à la télévision", "radio": "à la radio", "youtube": "sur YouTube", "twitch": "sur Twitch",
        "annonces": "avec invités annoncés", "web": "dans les agendas"}


def _collecter(args: argparse.Namespace, plateformes: list[str]) -> int:
    """Chaque source est indépendante : si l'une tombe, les autres continuent."""
    conf = _charger_config(args.config)
    if conf is None:
        return 1
    connexion = db.ouvrir(args.base)
    maintenant, fin = _horizon()
    reussites = []
    for p in plateformes:
        try:
            reussites.append(ETAPES[p](conf, connexion, maintenant, args))
        except Exception as e:  # une source cassée ne doit pas arrêter les autres
            print(f"  ERREUR inattendue ({type(e).__name__} : {e})")
            db.noter_collecte(connexion, p, maintenant, False, 0, [], f"erreur inattendue : {type(e).__name__} : {e}")
            reussites.append(False)
    # Les annonces complètent les émissions des autres sources : après elles, toute la grille.
    affichees = [p for p in plateformes if p in courriel.PLATEFORMES] or None
    emissions = affichage.emissions(connexion, maintenant, fin, affichees)
    connexion.close()
    ou = NOMS[plateformes[0]] if len(plateformes) == 1 and affichees else "toutes sources"
    print(f"\nÉmissions politiques {ou}, aujourd'hui et les 7 jours suivants : {len(emissions)}")
    afficher_grille(emissions)
    return 0 if all(reussites) else 1


def cmd_collecter_tv(args: argparse.Namespace) -> int:
    return _collecter(args, ["tv"])


def cmd_collecter_annonces(args: argparse.Namespace) -> int:
    return _collecter(args, ["annonces"])


def cmd_collecter_agendas(args: argparse.Namespace) -> int:
    return _collecter(args, ["web"])


def cmd_collecter_radio(args: argparse.Namespace) -> int:
    return _collecter(args, ["radio"])


def cmd_collecter_youtube(args: argparse.Namespace) -> int:
    return _collecter(args, ["youtube"])


def cmd_collecter_twitch(args: argparse.Namespace) -> int:
    return _collecter(args, ["twitch"])


def cmd_collecter(args: argparse.Namespace) -> int:
    return _collecter(args, ["tv", "radio", "youtube", "twitch", "web", "annonces"])


def _generer_page(args: argparse.Namespace) -> Path | None:
    try:
        conf = config.charger(args.config)
    except config.ErreurConfig as e:
        print(f"ERREUR de configuration : {e}")
        return None
    connexion = db.ouvrir(args.base)
    index = page.generer(connexion, conf, datetime.now(tv.PARIS), args.sortie)
    nb = connexion.execute("SELECT COUNT(*) FROM emissions WHERE statut != 'annulé'").fetchone()[0]
    connexion.close()
    print(f"Page générée : {index} ({nb} émissions en base)")
    return index


def cmd_page(args: argparse.Namespace) -> int:
    return 0 if _generer_page(args) else 1


def _adresse_locale() -> str:
    """Adresse du Mac sur le Wi-Fi ; un VPN actif fausserait la méthode générique."""
    import socket
    import subprocess

    for interface in ("en0", "en1"):  # Wi-Fi et Ethernet sur Mac
        try:
            adresse = subprocess.run(["ipconfig", "getifaddr", interface], capture_output=True, text=True,
                                     timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            break  # pas sur un Mac
        if adresse:
            return adresse
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 80))  # aucun paquet n'est envoyé
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def cmd_apercu(args: argparse.Namespace) -> int:
    """Génère la page et la sert sur le réseau local, pour l'ouvrir depuis le téléphone."""
    import functools
    import http.server

    index = _generer_page(args)
    if index is None:
        return 1
    gestionnaire = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(index.parent))
    with http.server.ThreadingHTTPServer(("0.0.0.0", args.port), gestionnaire) as serveur:
        print(f"\nSur ce Mac : http://localhost:{args.port}")
        print(f"Sur le téléphone (même Wi-Fi) : http://{_adresse_locale()}:{args.port}")
        print("Ctrl + C pour arrêter.")
        try:
            serveur.serve_forever()
        except KeyboardInterrupt:
            print("\nAperçu arrêté.")
    return 0


def cmd_chercher_tv(args: argparse.Namespace) -> int:
    """Montre comment une émission figure dans le guide et ce que le filtre en fait."""
    try:
        conf = config.charger(args.config)
    except config.ErreurConfig as e:
        print(f"ERREUR de configuration : {e}")
        return 1
    chemin = args.fichier
    if not chemin:
        try:
            chemin = tv.telecharger(requests.Session())
        except requests.RequestException as e:
            print(f"ERREUR guide télévision inaccessible ({e})")
            return 1
    try:
        resultats = tv.chercher(conf, chemin, args.texte, datetime.now(tv.PARIS))
    finally:
        if not args.fichier:
            chemin.unlink(missing_ok=True)
    print(f"{len(resultats)} programme(s) à venir contenant « {args.texte} » :")
    for r in resultats:
        print(f"\n  {JOURS[r['debut'].weekday()]} {r['debut']:%d/%m %H:%M}  {r['chaine']}")
        print(f"    Titre : {r['titre']}" + (f" — {r['sous_titre']}" if r["sous_titre"] else ""))
        if r["description"]:
            print(f"    Description : {r['description'][:160]}")
        print(f"    → {r['verdict']}")
    return 0


def cmd_courriel(args: argparse.Namespace) -> int:
    """Email du matin. Un seul envoi par jour, sauf --forcer. Aucune adresse n'est affichée (journaux publics)."""
    try:
        conf = config.charger(args.config)
    except config.ErreurConfig as e:
        print(f"ERREUR de configuration : {e}")
        return 1
    connexion = db.ouvrir(args.base)
    maintenant = datetime.now(tv.PARIS)
    jour = maintenant.date().isoformat()
    if not args.apercu and not args.forcer and db.deja_envoye(connexion, jour):
        print(f"Email du {jour} déjà envoyé : rien à faire.")
        return 0
    contenu = courriel.contenu(connexion, conf, maintenant)
    print(f"Email du {contenu['titre_jour']} : {len(contenu['aujourdhui'])} émission(s) aujourd'hui, "
          f"{len(contenu['temps_forts'])} temps fort(s), {len(contenu['alertes'])} alerte(s) sur les sources")
    if args.apercu:
        args.apercu.write_text(courriel.page_html(contenu), encoding="utf-8")
        print(f"Aperçu écrit dans {args.apercu} (rien n'a été envoyé)")
        return 0
    try:
        courriel.envoyer(courriel.message(contenu))
    except (courriel.ConfigurationEmailIncomplete, OSError, smtplib.SMTPException) as e:
        print(f"ERREUR envoi impossible : {e}")
        return 1
    db.noter_envoi(connexion, jour, datetime.now(tv.PARIS))
    connexion.close()
    print("Email envoyé.")
    return 0


def cmd_attente_7h(args: argparse.Namespace) -> int:
    """Affiche le nombre de secondes à attendre avant 7 h (heure de Paris), ou « hors-plage »."""
    attente = courriel.attente_avant_7h(datetime.now(tv.PARIS))
    print("hors-plage" if attente is None else int(attente))
    return 0


def cmd_lister(args: argparse.Namespace) -> int:
    connexion = db.ouvrir(args.base)
    maintenant, fin = _horizon()
    emissions = affichage.emissions(connexion, maintenant, fin)
    connexion.close()
    print(f"Émissions politiques, aujourd'hui et les 7 jours suivants : {len(emissions)}")
    afficher_grille(emissions)
    return 0


def charger_env(chemin: Path = Path(__file__).resolve().parent.parent / ".env") -> None:
    """Lit les secrets d'un fichier .env local (ignoré par Git), sans écraser l'environnement."""
    if not chemin.exists():
        return
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#") and "=" in ligne:
            cle, valeur = ligne.split("=", 1)
            os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


def main(argv: list[str] | None = None) -> int:
    charger_env()
    parser = argparse.ArgumentParser(prog="python -m grille", description="Grille politique Présidentielle 2027")
    parser.add_argument("--config", type=Path, default=config.DOSSIER_CONFIG, help="dossier des fichiers YAML")
    parser.add_argument("--base", type=Path, default=db.CHEMIN_BASE, help="fichier SQLite")
    sous = parser.add_subparsers(dest="commande", required=True)
    sous.add_parser("init", help="crée la base si besoin et lit la configuration").set_defaults(func=cmd_init)
    sous.add_parser("verifier-acces", help="teste le guide XMLTV et les API Radio France, YouTube et Twitch").set_defaults(
        func=cmd_verifier_acces
    )
    collecte = sous.add_parser("collecter-tv", help="lit le guide XMLTV, garde le politique, écrit en base, affiche")
    collecte.add_argument("--fichier", type=Path, help="guide déjà téléchargé (.xml ou .xml.gz) au lieu de xmltvfr.fr")
    collecte.add_argument("--motifs", action="store_true", help="affiche la règle qui a retenu chaque émission")
    collecte.set_defaults(func=cmd_collecter_tv)
    for nom, func, aide in [
        ("collecter-agendas", cmd_collecter_agendas, "agendas publiés par les partis et les candidats"),
        ("collecter-annonces", cmd_collecter_annonces, "invités annoncés dans les communiqués de France Télévisions"),
        ("collecter-radio", cmd_collecter_radio, "grille des stations Radio France (France Inter, franceinfo…)"),
        ("collecter-youtube", cmd_collecter_youtube, "directs YouTube programmés et en cours des chaînes suivies"),
        ("collecter-twitch", cmd_collecter_twitch, "chaînes Twitch en direct et plannings publiés"),
        ("collecter", cmd_collecter, "toutes les sources (télévision, radio, YouTube, Twitch, agendas, invités annoncés), chacune indépendamment"),
    ]:
        sp = sous.add_parser(nom, help=aide)
        sp.add_argument("--motifs", action="store_true", help="affiche la règle qui a retenu chaque émission")
        sp.set_defaults(func=func)
    sous.add_parser("lister", help="affiche la grille enregistrée en base").set_defaults(func=cmd_lister)
    p_courriel = sous.add_parser("courriel", help="envoie l'email du matin (une fois par jour)")
    p_courriel.add_argument("--apercu", type=Path, help="écrit l'email dans ce fichier HTML au lieu de l'envoyer")
    p_courriel.add_argument("--forcer", action="store_true", help="envoie même si l'email du jour est déjà parti")
    p_courriel.set_defaults(func=cmd_courriel)
    sous.add_parser("attente-7h", help="secondes à attendre avant 7 h, heure de Paris (pour la tâche GitHub)"
                    ).set_defaults(func=cmd_attente_7h)
    p_cherche = sous.add_parser("chercher-tv", help="cherche une émission dans le guide TV et dit si elle est retenue")
    p_cherche.add_argument("texte", help="mot ou titre à chercher (majuscules et accents ignorés)")
    p_cherche.add_argument("--fichier", type=Path, help="guide déjà téléchargé (.xml ou .xml.gz)")
    p_cherche.set_defaults(func=cmd_chercher_tv)
    p_page = sous.add_parser("page", help="génère la page web (dossier site/) depuis la base")
    p_page.add_argument("--sortie", type=Path, default=page.SORTIE, help="dossier de sortie")
    p_page.set_defaults(func=cmd_page)
    p_apercu = sous.add_parser("apercu", help="génère la page et l'affiche sur le réseau local (téléphone)")
    p_apercu.add_argument("--sortie", type=Path, default=page.SORTIE, help="dossier de sortie")
    p_apercu.add_argument("--port", type=int, default=8000)
    p_apercu.set_defaults(func=cmd_apercu)
    args = parser.parse_args(argv)
    return args.func(args)
