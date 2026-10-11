"""Cas douteux : émissions écartées par les filtres qui pourraient être politiques (mesure avant Claude)."""

import gzip
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from grille import config, courriel, db, tv
from grille.filtre import FiltrePolitique

EXTRAIT = Path(__file__).parent / "reponses" / "xmltv_tnt_extrait.xml"
MAINTENANT = datetime(2027, 3, 15, 10, 0, tzinfo=tv.PARIS)


@pytest.fixture
def conf():
    return config.charger()


@pytest.fixture
def connexion(tmp_path):
    c = db.ouvrir(tmp_path / "g.sqlite")
    yield c
    c.close()


def test_motifs(conf):
    f = FiltrePolitique(conf)
    assert f.motif_douteux("C à vous", "Anne-Élisabeth Lemoine reçoit ses invités.") == "émission à invités « C à vous »"
    assert f.motif_douteux("Le 20H", "Le gouvernement présente son budget.") == "« gouvernement »"
    # Parti au nom trop courant pour être un mot-clé : douteux, pas retenu.
    assert f.motif_douteux("La Renaissance italienne", "") == "« Renaissance »"
    assert f.motif_douteux("Koh-Lanta", "Les aventuriers affrontent l'épreuve des poteaux.") is None
    # « géopolitique » n'est pas « politique » (comparaison mot à mot).
    assert f.motif_douteux("Le dessous des cartes", "Un regard géopolitique.") is None


def test_collecte_tv_note_les_douteux_une_seule_fois(conf, connexion, tmp_path):
    chemin = tmp_path / "guide.xml.gz"
    chemin.write_bytes(gzip.compress(EXTRAIT.read_bytes()))
    rapport = tv.collecter(conf, chemin, connexion, MAINTENANT)
    cas = db.douteux_depuis(connexion, MAINTENANT - timedelta(hours=1))
    assert rapport.douteux == len(cas) > 0
    titres = {c["titre"] for c in cas}
    assert "La Renaissance italienne" in titres
    assert "Koh-Lanta" not in titres
    # Rien de retenu n'est douteux.
    assert not titres & {e["titre"] for e in rapport.retenues}
    # Deuxième collecte : les mêmes cas ne comptent plus comme nouveaux.
    assert tv.collecter(conf, chemin, connexion, MAINTENANT + timedelta(hours=1)).douteux == 0
    assert len(db.douteux_depuis(connexion, MAINTENANT + timedelta(minutes=30))) == 0


def test_email(conf, connexion):
    debut = (MAINTENANT + timedelta(hours=3)).isoformat()
    cas = [{"id": f"tv:x:{i}", "source": "tv", "chaine": "France 5", "titre": f"C à vous {i}", "description": "",
            "debut": debut, "motif": "émission à invités « C à vous »"} for i in range(12)]
    cas.append({"id": "youtube:1", "source": "youtube", "chaine": "Le Monde", "titre": "Le gouvernement en sursis",
                "description": "", "debut": debut, "motif": "« gouvernement »"})
    db.noter_douteux(connexion, cas, MAINTENANT - timedelta(hours=2))
    d = courriel.mesure_douteux(connexion, MAINTENANT)
    assert d["nombre"] == 13 and d["par_source"] == {"tv": 12, "youtube": 1}
    assert len(d["exemples"]) == 10
    assert any(x["motif"] == "« gouvernement »" for x in d["exemples"])  # motifs variés d'abord
    c = courriel.contenu(connexion, conf, MAINTENANT)
    assert "CAS DOUTEUX DES DERNIÈRES 24 H : 13 (12 télévision, 1 YouTube)" in courriel.texte(c)
    assert "Le gouvernement en sursis" in courriel.page_html(c)
    # Plus de 24 h après : la mesure ne les compte plus.
    assert courriel.mesure_douteux(connexion, MAINTENANT + timedelta(days=2))["nombre"] == 0
