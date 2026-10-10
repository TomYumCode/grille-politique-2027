"""Base SQLite : une table `emissions`, une ligne par diffusion.

Conventions de stockage :
- `debut`, `fin`, `vu_le` : texte ISO 8601 avec décalage, fuseau Europe/Paris
  (ex. 2027-03-15T21:00:00+01:00) ; `fin` peut être NULL.
- `invites` et `lien` : listes JSON, pour qu'une émission fusionnée porte
  plusieurs liens (télévision + YouTube, par exemple).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

CHEMIN_BASE = Path(__file__).resolve().parent.parent / "data" / "grille.sqlite"
VERSION_SCHEMA = 6

SCHEMA = """
CREATE TABLE IF NOT EXISTS emissions (
    id          TEXT PRIMARY KEY,                 -- source:identifiant d'origine, ex. youtube:abc123
    titre       TEXT NOT NULL,
    debut       TEXT NOT NULL,
    fin         TEXT,
    plateforme  TEXT NOT NULL CHECK (plateforme IN ('tv', 'radio', 'youtube', 'twitch', 'web')),
    chaine      TEXT NOT NULL,
    categorie   TEXT CHECK (categorie IN ('débat', 'interview', 'meeting', 'analyse')),
    invites     TEXT NOT NULL DEFAULT '[]',
    lien        TEXT NOT NULL DEFAULT '[]',
    statut      TEXT NOT NULL DEFAULT 'annoncé'
                CHECK (statut IN ('annoncé', 'en direct', 'terminé', 'annulé')),
    filtre      TEXT CHECK (filtre IN ('liste blanche', 'mots-clés', 'modèle')),
    vu_le       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS emissions_debut ON emissions (debut);

-- Version 2 (lot 3) : identifiants YouTube déjà résolus, pour ne pas dépenser de
-- quota à chaque collecte. Une ligne par adresse de chaines.yaml.
CREATE TABLE IF NOT EXISTS chaines_resolues (
    adresse     TEXT PRIMARY KEY,
    identifiant TEXT NOT NULL,                    -- UC… pour YouTube
    playlist    TEXT NOT NULL,                    -- playlist des vidéos mises en ligne (UU…)
    resolu_le   TEXT NOT NULL
);

-- Version 3 (lot 5) : compte rendu de chaque collecte, pour l'état des sources
-- dans l'email du matin, et date des emails envoyés (jamais deux le même jour).
CREATE TABLE IF NOT EXISTS collectes (
    horodatage  TEXT NOT NULL,
    source      TEXT NOT NULL,                    -- tv, radio, youtube, twitch
    reussie     INTEGER NOT NULL,                 -- 1 si la source a répondu
    retenues    INTEGER NOT NULL,
    anomalies   TEXT NOT NULL DEFAULT '[]',       -- liste JSON de messages
    erreur      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS collectes_horodatage ON collectes (horodatage);
CREATE TABLE IF NOT EXISTS envois (
    jour        TEXT PRIMARY KEY,                 -- AAAA-MM-JJ, heure de Paris
    envoye_le   TEXT NOT NULL
);

-- Version 6 (lot 6) : invités annoncés par communiqué de presse, appliqués à l'affichage.
CREATE TABLE IF NOT EXISTS annonces (
    id          TEXT PRIMARY KEY,                 -- identifiant du communiqué
    titre       TEXT NOT NULL,
    jour        TEXT NOT NULL,                    -- AAAA-MM-JJ
    heure       TEXT NOT NULL DEFAULT '',         -- HH:MM ou vide
    invites     TEXT NOT NULL DEFAULT '[]',
    url         TEXT NOT NULL,
    vu_le       TEXT NOT NULL
);

-- Version 4 : logo de chaque chaîne (adresse d'image fournie par la source).
CREATE TABLE IF NOT EXISTS logos (
    chaine      TEXT PRIMARY KEY,                 -- nom de la chaîne dans chaines.yaml
    url         TEXT NOT NULL,
    mis_a_jour  TEXT NOT NULL
);
"""


def ouvrir(chemin: Path = CHEMIN_BASE) -> sqlite3.Connection:
    """Ouvre la base et crée la table si besoin (sans effacer l'existant)."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    connexion = sqlite3.connect(chemin)
    connexion.executescript(SCHEMA)
    _accepter_la_radio(connexion)
    connexion.execute(f"PRAGMA user_version = {VERSION_SCHEMA}")
    connexion.commit()
    return connexion


def _accepter_la_radio(connexion: sqlite3.Connection) -> None:
    """Version 5 : plateforme « radio ». SQLite ne modifie pas une contrainte CHECK :
    la table d'une base plus ancienne est recopiée dans une table au nouveau schéma."""
    (sql,) = connexion.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'emissions'").fetchone()
    if "'radio'" in sql:
        return
    debut = SCHEMA.index("CREATE TABLE IF NOT EXISTS emissions")
    creation = SCHEMA[debut:SCHEMA.index(");", debut) + 2].replace("IF NOT EXISTS emissions", "emissions_v5")
    connexion.commit()
    connexion.executescript(f"""
        BEGIN;
        {creation}
        INSERT INTO emissions_v5 SELECT * FROM emissions;
        DROP TABLE emissions;
        ALTER TABLE emissions_v5 RENAME TO emissions;
        CREATE INDEX IF NOT EXISTS emissions_debut ON emissions (debut);
        COMMIT;
    """)


def enregistrer_collecte(
    connexion: sqlite3.Connection,
    emissions: list[dict],
    plateforme: str,
    chaines_couvertes: set[str],
    maintenant: datetime,
) -> int:
    """Écrit les émissions d'une collecte et renvoie le nombre d'émissions passées en « annulé ».

    Une émission déjà connue (même id) est mise à jour, pas recréée. Une émission
    à venir, d'une chaîne couverte par cette collecte, qui n'a pas été revue passe
    en « annulé ». Les chaînes absentes de la source ne sont pas touchées : une
    panne de source ne doit pas tout annuler.
    """
    vu_le = maintenant.isoformat(timespec="seconds")
    for e in emissions:
        connexion.execute(
            """
            INSERT INTO emissions (id, titre, debut, fin, plateforme, chaine, categorie, invites, lien, statut, filtre, vu_le)
            VALUES (:id, :titre, :debut, :fin, :plateforme, :chaine, :categorie, :invites, :lien, :statut, :filtre, :vu_le)
            ON CONFLICT (id) DO UPDATE SET
                titre = excluded.titre, debut = excluded.debut, fin = excluded.fin, chaine = excluded.chaine,
                categorie = excluded.categorie, invites = excluded.invites, lien = excluded.lien,
                statut = excluded.statut, filtre = excluded.filtre, vu_le = excluded.vu_le
            """,
            {**e, "invites": json.dumps(e["invites"], ensure_ascii=False),
             "lien": json.dumps(e["lien"], ensure_ascii=False), "vu_le": vu_le},
        )
    ids_vus = {e["id"] for e in emissions}
    annulees = [
        id_
        for id_, debut, chaine in connexion.execute(
            "SELECT id, debut, chaine FROM emissions WHERE plateforme = ? AND statut != 'annulé'", (plateforme,)
        )
        if id_ not in ids_vus and chaine in chaines_couvertes and datetime.fromisoformat(debut) > maintenant
    ]
    connexion.executemany("UPDATE emissions SET statut = 'annulé', vu_le = ? WHERE id = ?", [(vu_le, i) for i in annulees])
    connexion.commit()
    actualiser_statuts(connexion, maintenant)
    return len(annulees)


def lister(connexion: sqlite3.Connection, depuis: datetime, jusqua: datetime) -> list[dict]:
    """Émissions non annulées qui se terminent après `depuis` et commencent avant `jusqua`, par heure de début."""
    connexion.row_factory = sqlite3.Row
    lignes = [dict(r) for r in connexion.execute("SELECT * FROM emissions WHERE statut != 'annulé'")]
    connexion.row_factory = None
    resultat = []
    for e in lignes:
        debut = datetime.fromisoformat(e["debut"])
        fin = datetime.fromisoformat(e["fin"]) if e["fin"] else debut
        if fin > depuis and debut < jusqua:
            e["invites"], e["lien"] = json.loads(e["invites"]), json.loads(e["lien"])
            resultat.append(e)
    return sorted(resultat, key=lambda e: (datetime.fromisoformat(e["debut"]), e["chaine"]))


def actualiser_statuts(connexion: sqlite3.Connection, maintenant: datetime) -> None:
    """Passe en « terminé » les émissions annoncées ou en direct dont l'heure de fin est passée."""
    terminees = [
        i
        for i, fin in connexion.execute(
            "SELECT id, fin FROM emissions WHERE statut IN ('annoncé', 'en direct') AND fin IS NOT NULL"
        )
        if datetime.fromisoformat(fin) <= maintenant
    ]
    connexion.executemany("UPDATE emissions SET statut = 'terminé' WHERE id = ?", [(i,) for i in terminees])
    connexion.commit()


def terminer_directs(connexion: sqlite3.Connection, plateforme: str, ids_en_direct: set[str],
                     chaines_couvertes: set[str], maintenant: datetime) -> int:
    """Directs sans heure de fin qui ne sont plus diffusés : « terminé », fin = maintenant."""
    finis = [
        i
        for i, chaine in connexion.execute(
            "SELECT id, chaine FROM emissions WHERE plateforme = ? AND statut = 'en direct'", (plateforme,)
        )
        if i not in ids_en_direct and chaine in chaines_couvertes
    ]
    fin = maintenant.isoformat(timespec="seconds")
    connexion.executemany("UPDATE emissions SET statut = 'terminé', fin = ? WHERE id = ?", [(fin, i) for i in finis])
    connexion.commit()
    return len(finis)


def noter_collecte(connexion: sqlite3.Connection, source: str, maintenant: datetime, reussie: bool,
                   retenues: int, anomalies: list[str], erreur: str = "") -> None:
    connexion.execute(
        "INSERT INTO collectes VALUES (?, ?, ?, ?, ?, ?)",
        (maintenant.isoformat(timespec="seconds"), source, int(reussie), retenues,
         json.dumps(anomalies, ensure_ascii=False), erreur),
    )
    # On ne garde que 30 jours de comptes rendus.
    limite = (maintenant - timedelta(days=30)).isoformat(timespec="seconds")
    connexion.execute("DELETE FROM collectes WHERE horodatage < ?", (limite,))
    connexion.commit()


def etat_des_sources(connexion: sqlite3.Connection, maintenant: datetime, sources: dict[str, str]) -> list[str]:
    """Alertes : source sans collecte réussie depuis 24 h, anomalies de la dernière collecte réussie.

    `sources` : identifiant → nom affiché, par exemple {"tv": "Télévision"}.
    """
    alertes = []
    depuis = maintenant - timedelta(hours=24)
    for source, nom in sources.items():
        lignes = [
            (datetime.fromisoformat(h), bool(r), json.loads(a), e)
            for h, r, a, e in connexion.execute(
                "SELECT horodatage, reussie, anomalies, erreur FROM collectes WHERE source = ? ORDER BY horodatage",
                (source,),
            )
        ]
        recentes = [ligne for ligne in lignes if ligne[0] >= depuis]
        reussies = [ligne for ligne in recentes if ligne[1]]
        if not reussies:
            derniere = recentes[-1][3] if recentes else "aucune collecte enregistrée"
            alertes.append(f"{nom} : aucune collecte réussie depuis 24 h ({derniere})")
            continue
        alertes.extend(f"{nom} : {a}" for a in reussies[-1][2])
    return alertes


def deja_envoye(connexion: sqlite3.Connection, jour: str) -> bool:
    return connexion.execute("SELECT 1 FROM envois WHERE jour = ?", (jour,)).fetchone() is not None


def noter_envoi(connexion: sqlite3.Connection, jour: str, maintenant: datetime) -> None:
    connexion.execute("INSERT OR REPLACE INTO envois VALUES (?, ?)", (jour, maintenant.isoformat(timespec="seconds")))
    connexion.commit()


def noter_logos(connexion: sqlite3.Connection, logos: dict[str, str], maintenant: datetime) -> None:
    """Mémorise les logos (nom de chaîne → adresse d'image).

    Une adresse vide est gardée aussi : elle note que la source n'a pas de logo,
    pour ne pas le redemander (et dépenser du quota) à chaque collecte.
    """
    horodatage = maintenant.isoformat(timespec="seconds")
    connexion.executemany(
        "INSERT OR REPLACE INTO logos VALUES (?, ?, ?)",
        [(chaine, url or "", horodatage) for chaine, url in logos.items()],
    )
    connexion.commit()


def noter_annonces(connexion: sqlite3.Connection, annonces: list[dict], maintenant: datetime) -> None:
    """Mémorise les annonces d'invités ; oublie celles de plus de 8 jours."""
    vu_le = maintenant.isoformat(timespec="seconds")
    connexion.executemany(
        "INSERT OR REPLACE INTO annonces VALUES (:id, :titre, :jour, :heure, :invites, :url, :vu_le)",
        [{**a, "invites": json.dumps(a["invites"], ensure_ascii=False), "vu_le": vu_le} for a in annonces],
    )
    connexion.execute("DELETE FROM annonces WHERE jour < ?", ((maintenant - timedelta(days=8)).date().isoformat(),))
    connexion.commit()


def annonces(connexion: sqlite3.Connection) -> list[dict]:
    lignes = connexion.execute("SELECT id, titre, jour, heure, invites, url FROM annonces").fetchall()
    return [{"id": i, "titre": t, "jour": j, "heure": h, "invites": json.loads(n), "url": u} for i, t, j, h, n, u in lignes]


def logos(connexion: sqlite3.Connection, avec_vides: bool = False) -> dict[str, str]:
    """Nom de chaîne → adresse du logo (les chaînes sans logo seulement si `avec_vides`)."""
    return {c: u for c, u in connexion.execute("SELECT chaine, url FROM logos") if u or avec_vides}
