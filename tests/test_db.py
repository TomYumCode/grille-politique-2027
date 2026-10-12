import sqlite3

import pytest

from grille import db


def test_ouvrir_cree_une_base_vide_et_reste_idempotent(tmp_path):
    chemin = tmp_path / "sous-dossier" / "grille.sqlite"
    db.ouvrir(chemin).close()
    connexion = db.ouvrir(chemin)
    colonnes = [ligne[1] for ligne in connexion.execute("PRAGMA table_info(emissions)")]
    assert colonnes == [
        "id", "titre", "debut", "fin", "plateforme", "chaine", "categorie",
        "invites", "lien", "statut", "filtre", "vu_le", "cites", "resume",
    ]
    assert connexion.execute("SELECT COUNT(*) FROM emissions").fetchone()[0] == 0
    assert connexion.execute("PRAGMA user_version").fetchone()[0] == db.VERSION_SCHEMA


@pytest.mark.parametrize("plateformes", ["'tv', 'youtube', 'twitch'", "'tv', 'radio', 'youtube', 'twitch', 'web'"])
def test_base_ancienne_mise_a_niveau(tmp_path, plateformes):
    """Base d'avant la version 8 (et d'avant la radio) : colonnes ajoutées, émissions gardées."""
    chemin = tmp_path / "g.sqlite"
    ancienne = sqlite3.connect(chemin)
    ancienne.executescript(f"""
        CREATE TABLE emissions (id TEXT PRIMARY KEY, titre TEXT NOT NULL, debut TEXT NOT NULL, fin TEXT,
            plateforme TEXT NOT NULL CHECK (plateforme IN ({plateformes})), chaine TEXT NOT NULL,
            categorie TEXT, invites TEXT NOT NULL DEFAULT '[]', lien TEXT NOT NULL DEFAULT '[]',
            statut TEXT NOT NULL DEFAULT 'annoncé', filtre TEXT, vu_le TEXT NOT NULL);
        INSERT INTO emissions (id, titre, debut, plateforme, chaine, invites, vu_le)
            VALUES ('tv:1', 'Franc-jeu', '2027-03-15T21:00:00+01:00', 'tv', 'France 2', '["Gabriel Attal"]',
                    '2027-03-15T20:00:00+01:00');
    """)
    ancienne.close()
    connexion = db.ouvrir(chemin)
    from datetime import datetime
    (e,) = db.lister(connexion, datetime.fromisoformat("2027-03-15T00:00:00+01:00"),
                     datetime.fromisoformat("2027-03-16T00:00:00+01:00"))
    assert (e["invites"], e["cites"], e["resume"]) == (["Gabriel Attal"], [], "")
    connexion.close()


def test_valeurs_hors_liste_refusees(tmp_path):
    connexion = db.ouvrir(tmp_path / "g.sqlite")
    with pytest.raises(sqlite3.IntegrityError):
        connexion.execute(
            "INSERT INTO emissions (id, titre, debut, plateforme, chaine, vu_le) VALUES (?, ?, ?, ?, ?, ?)",
            ("fax:1", "x", "2027-03-15T21:00:00+01:00", "fax", "x", "2027-03-15T20:00:00+01:00"),
        )
