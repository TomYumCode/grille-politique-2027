import textwrap

import pytest

from grille import config


def test_configuration_du_depot_sans_anomalie():
    conf = config.charger()
    assert conf.anomalies == []
    # Le nombre exact varie au fil des ajouts et retraits dans chaines.yaml.
    assert sum(c.plateforme == "tv" for c in conf.chaines) == 11
    assert len(conf.chaines) > 100
    assert {c.plateforme for c in conf.chaines} == {"tv", "radio", "youtube", "twitch", "web"}
    assert "Mélenchon" in conf.noms_a_reperer()


@pytest.mark.parametrize(
    "plateforme, adresse, attendu",
    [
        ("youtube", "https://www.youtube.com/@Clemovitch", {"handle": "Clemovitch"}),
        ("youtube", "https://www.youtube.com/channel/UCAcAnMF0OrCtUep3Y4M-ZPw", {"channel_id": "UCAcAnMF0OrCtUep3Y4M-ZPw"}),
        ("youtube", "https://www.youtube.com/user/hecparis", {"user": "hecparis"}),
        ("youtube", "https://www.youtube.com/c/brutofficiel", {"custom": "brutofficiel"}),
        ("twitch", "https://www.twitch.tv/JeanMassiet", {"login": "jeanmassiet"}),
        ("tv", "France2.fr", {"xmltv_id": "France2.fr"}),
        ("radio", "FRANCEINTER", {"station": "FRANCEINTER"}),
        ("radio", "France Inter", None),
        ("youtube", "https://www.twitch.tv/jeanmassiet", None),
        ("twitch", "https://www.twitch.tv/", None),
    ],
)
def test_analyser_adresse(plateforme, adresse, attendu):
    assert config.analyser_adresse(plateforme, adresse) == attendu


def _ecrire(dossier, chaines, politique="candidats: [{nom: A}]\n"):
    (dossier / "chaines.yaml").write_text(textwrap.dedent(chaines), encoding="utf-8")
    (dossier / "politique.yaml").write_text(politique, encoding="utf-8")


def test_ligne_invalide_signalee_sans_bloquer_les_autres(tmp_path):
    _ecrire(
        tmp_path,
        """\
        chaines:
        - {plateforme: youtube, nom: "Bonne", adresse: "https://www.youtube.com/@bonne", categorie: "X"}
        - {plateforme: youtube, nom: "Mauvaise", adresse: "youtube.com/bonne", categorie: "X"}
        - {plateforme: radio, nom: "Inconnue", adresse: "x", categorie: "X"}
        - {plateforme: twitch, nom: "Sans catégorie", adresse: "https://www.twitch.tv/abc"}
        - {plateforme: youtube, nom: "Doublon", adresse: "https://www.youtube.com/@Bonne", categorie: "X"}
        """,
    )
    conf = config.charger(tmp_path)
    assert [c.nom for c in conf.chaines] == ["Bonne"]
    assert len(conf.anomalies) == 4
    assert "Mauvaise" in conf.anomalies[0]


def test_yaml_casse_est_bloquant(tmp_path):
    _ecrire(tmp_path, "chaines:\n- {plateforme: tv, nom: \"F2\"\n")
    with pytest.raises(config.ErreurConfig, match="YAML invalide"):
        config.charger(tmp_path)


def test_fichier_absent_est_bloquant(tmp_path):
    with pytest.raises(config.ErreurConfig, match="introuvable"):
        config.charger(tmp_path)


def test_plusieurs_liens_de_direct(tmp_path):
    _ecrire(
        tmp_path,
        """\
        chaines:
        - {plateforme: tv, nom: "Une", adresse: "Une.fr", categorie: "X", direct: "https://une.fr/direct"}
        - {plateforme: tv, nom: "Deux", adresse: "Deux.fr", categorie: "X", direct: ["https://a.fr/direct", "pas une adresse"]}
        """,
    )
    conf = config.charger(tmp_path)
    assert [c.direct for c in conf.chaines] == [("https://une.fr/direct",), ("https://a.fr/direct",)]
    assert any("pas une adresse" in a for a in conf.anomalies)
