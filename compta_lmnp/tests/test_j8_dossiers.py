# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Tests J8 — multi-dossiers : registre, sécurité du cookie, isolation des
comptabilités, aller-retour bac à sable.
Lancer :  pytest -q tests/test_j8_dossiers.py
"""
import importlib
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import dossiers
import init_db

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")


# === Registre ==============================================================

def test_slugifier_accents_et_espaces():
    assert dossiers.slugifier("Mon T2 à Nancy !") == "mon-t2-a-nancy"
    assert dossiers.slugifier("Éléonore & fils") == "eleonore-fils"


@pytest.mark.parametrize("nom", ["", "   ", "!!!", "../../etc/passwd", "…"])
def test_slugifier_rejette_les_noms_inutilisables(nom):
    # « ../../etc/passwd » se réduit à « etc-passwd » : inoffensif ; les
    # noms sans aucun caractère utilisable, eux, sont rejetés.
    if nom == "../../etc/passwd":
        assert dossiers.slugifier(nom) == "etc-passwd"
    else:
        with pytest.raises(ValueError):
            dossiers.slugifier(nom)


def test_creer_lister_renommer(tmp_path):
    racine = str(tmp_path)
    d = dossiers.creer(racine, "Studio Nancy", annee_cible=2026)
    assert d["slug"] == "studio-nancy"
    assert os.path.exists(d["chemin"])                    # base initialisée
    assert os.path.dirname(d["chemin"]).endswith(os.path.join("dossiers",
                                                              "studio-nancy"))
    liste = dossiers.lister(racine, os.path.join(racine, "compta.db"))
    assert [e["slug"] for e in liste] == ["principal", "studio-nancy"]

    dossiers.renommer(racine, "studio-nancy", "Studio Nancy Centre")
    assert dossiers.nom(racine, "studio-nancy") == "Studio Nancy Centre"


def test_creer_refuse_doublon_et_reserves(tmp_path):
    racine = str(tmp_path)
    dossiers.creer(racine, "Studio Nancy", annee_cible=2026)
    with pytest.raises(ValueError):
        dossiers.creer(racine, "studio nancy", annee_cible=2026)   # même slug
    with pytest.raises(ValueError):
        dossiers.creer(racine, "Principal", annee_cible=2026)      # réservé
    with pytest.raises(ValueError):
        dossiers.creer(racine, "Bac à sable", annee_cible=2026)    # réservé


def test_chemin_db_ne_vient_que_du_registre(tmp_path):
    racine = str(tmp_path)
    assert dossiers.chemin_db(racine, "inconnu") is None
    assert not dossiers.slug_sur("../../evil")
    assert not dossiers.slug_sur("bac_a_sable")
    assert not dossiers.slug_sur("")


# === Intégration web =======================================================

@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = str(tmp_path / "compta.db")
    init_db.init_demo(db, FEC2025, 2026).close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "bac.db"))
    import app as app_mod
    importlib.reload(app_mod)
    # Le registre J8 vit à côté de app.py : on l'isole aussi dans tmp_path.
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    yield app_mod.app.test_client(), app_mod, str(tmp_path)
    monkeypatch.delenv("COMPTA_DB")
    monkeypatch.delenv("COMPTA_DB_BAC_A_SABLE")
    importlib.reload(app_mod)


def test_creation_ouvre_le_dossier_et_isole_les_donnees(client):
    c, app_mod, racine = client
    # Le dossier principal (démo) montre l'exercice 2026 repris du FEC réel.
    assert "2025" in c.get("/liasse?annee=2025").get_data(as_text=True)

    rep = c.post("/dossiers/creer", data={"nom": "Studio Nancy"},
                 follow_redirects=False)
    assert rep.status_code == 302
    assert "studio-nancy" in rep.headers.get("Set-Cookie", "")

    # Le nouveau dossier est vierge : aucune écriture, en-tête à son nom.
    page = c.get("/dossiers").get_data(as_text=True)
    assert "Studio Nancy" in page and "actif" in page
    import sqlite3
    with app_mod.app.test_request_context(headers={
            "Cookie": "dossier=studio-nancy"}):
        chemin = app_mod._db_path()
    assert os.path.join("dossiers", "studio-nancy") in chemin
    n = sqlite3.connect(chemin).execute(
        "SELECT COUNT(*) FROM ecriture").fetchone()[0]
    assert n == 0                                   # isolation : base vierge


def test_cookie_forge_retombe_sur_le_principal(client):
    c, app_mod, _racine = client
    for forge in ("../../etc/passwd", "x/../y", "inconnu", "bac_a_sable/../a"):
        c.set_cookie("dossier", forge)
        rep = c.get("/dossiers")
        assert rep.status_code == 200
        with app_mod.app.test_request_context(headers={
                "Cookie": f"dossier={forge}"}):
            assert app_mod._db_path() == app_mod.DB   # jamais un chemin forgé


def test_ouvrir_dossier_inconnu_refuse(client):
    c, _app_mod, _racine = client
    rep = c.post("/dossiers/ouvrir", data={"slug": "fantome"},
                 follow_redirects=False)
    assert "err=" in rep.headers["Location"]


def test_bac_a_sable_revient_au_dossier_d_origine(client):
    c, _app_mod, _racine = client
    c.post("/dossiers/creer", data={"nom": "Studio Nancy"})
    c.post("/bac-a-sable/activer")
    page = c.get("/saisie").get_data(as_text=True)
    assert "BAC À SABLE" in page
    c.post("/bac-a-sable/quitter")
    page = c.get("/dossiers").get_data(as_text=True)
    # De retour dans Studio Nancy : c'est LUI que l'en-tête affiche comme
    # dossier actif — pas le principal, pas le bac à sable.
    entete = page.split("<main")[0]
    assert "Studio Nancy" in entete and "bac à sable" not in entete


def test_renommer_via_le_web(client):
    c, _app_mod, _racine = client
    c.post("/dossiers/creer", data={"nom": "Studio Nancy"})
    c.post("/dossiers/renommer", data={"slug": "studio-nancy",
                                       "nom": "T2 Nancy Centre"})
    assert "T2 Nancy Centre" in c.get("/dossiers").get_data(as_text=True)
