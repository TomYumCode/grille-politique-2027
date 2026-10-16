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


def test_derniere_collecte_et_commandes_pour_github(tmp_path, capsys):
    """« collecte-recente » et « envoi-du-jour » : la tâche GitHub ne refait pas ce qui est fait."""
    from datetime import datetime, timedelta

    from grille import cli
    from grille.tv import PARIS

    chemin = tmp_path / "g.sqlite"
    connexion = db.ouvrir(chemin)
    assert db.derniere_collecte(connexion) is None
    maintenant = datetime.now(PARIS)
    db.noter_collecte(connexion, "tv", maintenant - timedelta(minutes=10), True, 3, [])
    connexion.commit()
    assert db.derniere_collecte(connexion) == (maintenant - timedelta(minutes=10)).replace(microsecond=0)
    connexion.close()

    cli.main(["--base", str(chemin), "collecte-recente", "--minutes", "40"])
    cli.main(["--base", str(chemin), "collecte-recente", "--minutes", "5"])
    cli.main(["--base", str(chemin), "envoi-du-jour"])
    connexion = db.ouvrir(chemin)
    db.noter_envoi(connexion, maintenant.date().isoformat(), maintenant)
    connexion.close()
    cli.main(["--base", str(chemin), "envoi-du-jour"])
    assert capsys.readouterr().out.split() == ["oui", "non", "a-faire", "fait"]


def test_oublier_les_donnees_non_relues(tmp_path):
    """Twitch : 24 heures ; YouTube : 30 jours (conditions des API). Les autres plateformes restent."""
    from datetime import datetime, timedelta

    from grille.tv import PARIS

    connexion = db.ouvrir(tmp_path / "g.sqlite")
    maintenant = datetime(2026, 10, 16, 12, 0, tzinfo=PARIS)

    def emission(id_, plateforme, vu_le):
        db.enregistrer_collecte(connexion, [{
            "id": id_, "titre": "x", "debut": (maintenant + timedelta(days=1)).isoformat(), "fin": None,
            "plateforme": plateforme, "chaine": "c", "categorie": "analyse", "invites": [], "lien": [],
            "statut": "annoncé", "filtre": "mots-clés"}], plateforme, set(), vu_le)

    emission("twitch:vieux", "twitch", maintenant - timedelta(hours=25))
    emission("twitch:frais", "twitch", maintenant - timedelta(hours=2))
    emission("tv:vieux", "tv", maintenant - timedelta(days=40))
    assert db.oublier(connexion, "twitch", timedelta(hours=24), maintenant) == 1
    ids = {i for (i,) in connexion.execute("SELECT id FROM emissions")}
    assert ids == {"twitch:frais", "tv:vieux"}
    connexion.close()
