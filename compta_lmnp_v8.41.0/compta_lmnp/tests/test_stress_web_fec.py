# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Stress test couche web + validateur FEC (contrôles DGFiP Test Compta Demat).

Failles web corrigées :
  1. année/montant non numériques → erreur serveur 500 avec fuite de
     traceback ; désormais message clair (helpers de parsing tolérants) ;
  2. aucune limite de taille de requête ni filet d'erreur global.

Contrôles FEC ajoutés (vérifiés contre les FEC réels 2023-2025 qui doivent
rester conformes) : CompteNum ≥ 3 caractères, lettrage cohérent
(DateLet ⇒ EcritureLet), nomenclature de fichier SirenFECAAAAMMJJ.txt.
Piège évité : le rejet des montants négatifs, qui aurait produit des faux
positifs (les à-nouveaux réels en contiennent).

Lancer :  pytest -q tests/test_stress_web_fec.py
"""
import importlib
import os
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import init_db
import valider_fec

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")


# === Couche web ============================================================

@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = str(tmp_path / "compta.db")
    init_db.init_demo(db, FEC2025, 2026).close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "bac.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    yield app_mod.app.test_client(), app_mod, db
    monkeypatch.delenv("COMPTA_DB")
    monkeypatch.delenv("COMPTA_DB_BAC_A_SABLE")
    importlib.reload(app_mod)


@pytest.mark.parametrize("data", [
    {"annee": "xxxx", "forcer": "1"},        # année non entière
    {"annee": "", "forcer": "1"},            # année vide
    {"annee": "2026.5", "forcer": "1"},      # année décimale
])
def test_cloturer_annee_invalide_ne_500_pas(client, data):
    c, _app, _db = client
    r = c.post("/cloturer", data=data)
    assert r.status_code != 500          # message clair, pas de traceback
    assert r.status_code in (302, 400)


@pytest.mark.parametrize("montant", ["abc", "nan", "inf", "", "1e999"])
def test_saisir_montant_invalide_ne_500_pas(client, montant):
    c, _app, _db = client
    r = c.post("/saisir", data={"type": "loyer", "montant": montant,
                                "date_operation": "2026-03-01"})
    assert r.status_code != 500


def test_saisir_nan_ne_touche_pas_la_base(client):
    import sqlite3
    c, _app, db = client
    c.post("/saisir", data={"type": "loyer", "montant": "nan",
                            "date_operation": "2026-03-01"})
    n = sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM ligne WHERE debit != debit OR credit != credit"
    ).fetchone()[0]
    assert n == 0                        # aucun NaN stocké


def test_virgule_francaise_acceptee(client):
    c, _app, db = client
    import sqlite3
    c.post("/saisir", data={"type": "loyer", "montant": "795,50",
                            "date_operation": "2026-03-01"})
    m = sqlite3.connect(db).execute(
        "SELECT montant FROM operation ORDER BY id DESC LIMIT 1").fetchone()
    assert m and abs(m[0] - 795.50) < 0.005


def test_exercice_ouvrir_annee_invalide_ne_500_pas(client):
    c, _app, _db = client
    r = c.post("/exercice/ouvrir", data={"annee": "zz",
               "date_debut": "2027-01-01", "date_fin": "2027-12-31"})
    assert r.status_code != 500


def test_requete_trop_grosse_refusee(client):
    c, _app, _db = client
    r = c.post("/saisir", data={"type": "loyer", "montant": "795",
               "date_operation": "2026-03-01", "libelle": "A" * 3_000_000})
    assert r.status_code == 413         # au-delà du plafond de 2 Mo


def test_route_inexistante_404(client):
    c, _app, _db = client
    assert c.get("/route-qui-nexiste-pas").status_code == 404


# === Validateur FEC : contrôles DGFiP ======================================

EN = "\t".join(valider_fec.COLONNES)


def _fec(lignes):
    f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                    encoding="utf-8")
    f.write(EN + "\n")
    for ligne in lignes:
        f.write("\t".join(ligne) + "\n")
    f.close()
    return f.name


def _l(num="1", cn="706000", d="", c="", let="", datelet="",
       ed="20260301", vd="20260301", pd="20260301"):
    return ["BQ", "Banque", num, ed, cn, "Libellé compte", "", "", "P1", pd,
            "libellé", d, c, let, datelet, vd, "", ""]


def test_compte_trop_court_rejete():
    errs = valider_fec.valider(_fec([_l(cn="70", d="100"),
                                     _l(cn="512000", c="100")]))
    assert any("trop court" in e for e in errs)


def test_lettrage_incoherent_rejete():
    errs = valider_fec.valider(_fec([_l(datelet="20260401", d="100"),
                                     _l(cn="512000", c="100")]))
    assert any("lettrage incohérent" in e for e in errs)


def test_lettrage_complet_accepte():
    errs = valider_fec.valider(_fec([
        _l(let="AAA", datelet="20260401", d="100"),
        _l(cn="512000", let="AAA", datelet="20260401", c="100")]))
    assert errs == []


def test_montant_negatif_accepte_car_present_dans_les_anouveaux_reels():
    # Piège de l'audit : NE PAS rejeter les négatifs (faux positifs).
    errs = valider_fec.valider(_fec([_l(d="-100"), _l(cn="512000", c="-100")]))
    assert not any("négatif" in e for e in errs)


def test_separateur_point_toujours_rejete():
    errs = valider_fec.valider(_fec([_l(d="100.00"),
                                     _l(cn="512000", c="100.00")]))
    assert any("interdit" in e for e in errs)


@pytest.mark.parametrize("nom,conforme", [
    ("123456789FEC20251231.txt", True),
    ("123456789FEC20231231.txt", True),
    ("mon_fec.txt", False),
    ("12345FEC20251231.txt", False),        # SIREN trop court
    ("123456789FEC20261332.txt", False),    # date impossible
])
def test_nomenclature_fichier(nom, conforme):
    res = valider_fec.valider_nom_fichier(nom)
    assert (res is None) == conforme


@pytest.mark.parametrize("annee", [2023, 2024, 2025])
def test_les_fec_reels_restent_conformes(annee):
    """Garde-fou anti-régression : les FEC réels acceptés par l'administration
    ne doivent JAMAIS être rejetés par un durcissement du validateur."""
    ref = os.path.join(HERE, "reference", f"FEC_REFERENCE_{annee}.txt")
    assert valider_fec.valider(ref) == []


# === Revue finale A47 A-1 (points fins) ====================================

def test_champs_obligatoires_par_ligne_detectes():
    """ValidDate vide → anomalie (colonne obligatoire)."""
    errs = valider_fec.valider(_fec([_l(vd="", d="100"),
                                     _l(cn="512000", c="100")]))
    assert any("ValidDate vide" in e for e in errs)


def test_compaux_desapparie_detecte():
    lg = _l(d="100")
    lg[6] = "CLI001"                            # CompAuxNum sans CompAuxLib
    errs = valider_fec.valider(_fec([lg, _l(cn="512000", c="100")]))
    assert any("CompAuxNum" in e for e in errs)


def test_devise_desappariee_detectee():
    lg = _l(d="100")
    lg[16] = "100,00"                           # Montantdevise sans Idevise
    errs = valider_fec.valider(_fec([lg, _l(cn="512000", c="100")]))
    assert any("Idevise" in e for e in errs)


def test_export_sans_bom_et_crlf_homogene(tmp_path):
    """Le FEC généré reproduit la convention des FEC réels acceptés :
    UTF-8 sans BOM, fins de ligne CRLF homogènes."""
    import fiscal
    import operations
    db = str(tmp_path / "x.db")
    conn = init_db.init_demo(db, FEC2025, 2026)
    operations.saisir(conn, type="loyer", montant=795.50,
                      date_operation="2026-02-05", bien_id=1,
                      libelle="Loyer février — Müller & Cie")
    fiscal.cloturer(conn, 2026)
    import export_fec
    fec = str(tmp_path / "123456789FEC20261231.txt")
    export_fec.exporter(conn, 2026, fec)
    conn.close()
    brut = open(fec, "rb").read()
    assert not brut.startswith(b"\xef\xbb\xbf")           # pas de BOM
    assert brut.count(b"\n") == brut.count(b"\r\n")       # CRLF homogène
    texte = brut.decode("utf-8")                          # UTF-8 strict
    assert "Müller" in texte and "février" in texte       # accents intacts
    assert valider_fec.valider(fec) == []


def test_montant_extreme_serialise_en_clair(tmp_path):
    """Un montant de 10 milliards ne doit jamais partir en notation
    scientifique dans le FEC."""
    import fiscal
    import operations
    import export_fec
    conn = init_db.init_demo(str(tmp_path / "y.db"), FEC2025, 2026)
    operations.saisir(conn, type="loyer", montant=9_999_999_999.99,
                      date_operation="2026-03-05", bien_id=1)
    fiscal.cloturer(conn, 2026)
    fec = str(tmp_path / "z.txt")
    export_fec.exporter(conn, 2026, fec)
    conn.close()
    contenu = open(fec, encoding="utf-8").read()
    assert "9999999999,99" in contenu
    assert "e+" not in contenu.lower() or "E+" not in contenu
