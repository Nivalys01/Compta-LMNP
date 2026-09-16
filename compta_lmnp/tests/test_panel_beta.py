# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Panel de bêta-testeurs simulé (v8.7.0) — constats figés en non-régression.

Cinq personas rejoués sur le paquet client :
  - Michel (novice)  : BLOQUANT — aucune correction d'opération possible
    → annulation par CONTRE-PASSATION (écriture inverse, jamais de
    suppression : numérotation FEC dense, piste d'audit complète) ;
  - Sandrine (pressée) : BLOQUANT — import bancaire FANTÔME (module durci
    en v7.4, jamais câblé dans l'interface) → import en deux temps
    (propositions puis validation des lignes cochées) ;
  - Nadia (migrante depuis un logiciel du marché) : BLOQUANT — rejeu_fec inaccessible → reprise
    d'un exercice complet depuis son FEC, page Nouvel exercice ;
  - Karim (maladroit) : le doublon du double-clic est rattrapé par le
    contrôle pré-clôture (vérifié) ; messages de format clairs ;
  - Paul (anxieux) : la page Clôture dit désormais que la clôture se
    restaure en un clic ; saisie sans bien = message d'orientation, plus
    de « FOREIGN KEY constraint failed ».

Lancer :  pytest -q tests/test_panel_beta.py
"""
import importlib
import io
import os
import re
import sqlite3
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import controles
import fiscal
import init_db
import migrations
import operations

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")


@pytest.fixture()
def conn(tmp_path):
    c = init_db.init_demo(str(tmp_path / "p.db"), FEC2025, 2026)
    yield c
    c.close()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = str(tmp_path / "compta.db")
    init_db.init(db, "blanc", annee_cible=2026).close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "bac.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    cl = app_mod.app.test_client()
    cl.post("/immobilisations/exploitant", data={
        "nom": "MARTIN Michel", "siren": "512345678", "adresse": "Vichy"})
    cl.post("/immobilisations/bien", data={
        "libelle": "T2 Vichy", "adresse": "8 av Thermale",
        "date_acquisition": "2020-06-01", "prix_acquisition": "120000",
        "quote_part_terrain": "12000"})
    yield cl, db
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


# === Michel : annulation par contre-passation ==============================

def test_annulation_neutralise_l_ecriture(conn):
    avant = conn.execute("SELECT COUNT(*) FROM ecriture "
                         "WHERE exercice_annee=2026").fetchone()[0]
    r = operations.saisir(conn, type="loyer", montant=7800, periode="2026-02",
                          date_operation="2026-02-05", bien_id=1)
    operations.annuler(conn, r["operation_id"])
    solde = conn.execute(
        "SELECT ROUND(SUM(l.debit-l.credit),2) FROM ligne l "
        "JOIN ecriture e ON e.id=l.ecriture_id "
        "WHERE e.exercice_annee=2026 AND l.compte_num='708810'").fetchone()[0]
    assert solde == 0.0
    # rien n'est supprimé : l'erreur ET sa contre-passation existent
    apres = conn.execute("SELECT COUNT(*) FROM ecriture "
                         "WHERE exercice_annee=2026").fetchone()[0]
    assert apres == avant + 2


def test_annulation_sort_des_agregats_fiscaux(conn):
    ok = operations.saisir(conn, type="loyer", montant=780, periode="2026-01",
                           date_operation="2026-01-05", bien_id=1)
    erreur = operations.saisir(conn, type="loyer", montant=7800,
                               periode="2026-02", date_operation="2026-02-05",
                               bien_id=1)
    del ok
    operations.annuler(conn, erreur["operation_id"])
    res = fiscal.cloturer(conn, 2026)
    # seuls les 780 « vrais » subsistent dans les produits
    produits = conn.execute(
        "SELECT ROUND(SUM(l.credit-l.debit),2) FROM ligne l "
        "JOIN ecriture e ON e.id=l.ecriture_id "
        "WHERE e.exercice_annee=2026 AND l.compte_num='708810'").fetchone()[0]
    assert produits == 780.0
    assert res["agregats"]["resultat_comptable"] < 780.0


def test_annulation_exclue_des_controles_et_de_l_alur(conn):
    alur = operations.saisir(conn, type="fonds_travaux_alur", montant=95,
                             date_operation="2026-04-20", bien_id=1)
    operations.annuler(conn, alur["operation_id"])
    operations.saisir(conn, type="loyer", montant=780, periode="2026-01",
                      date_operation="2026-01-05", bien_id=1)
    res = fiscal.cloturer(conn, 2026)
    s = res["suivi_39c"]
    sans = round(res["agregats"]["resultat_comptable"]
                 + s["report_annee"] - s["utilisation_annee"], 2)
    assert res["resultat_fiscal"] == pytest.approx(sans, abs=0.01), \
        "un fonds ALUR annulé ne doit PAS être réintégré"


def test_annulation_refusee_sur_exercice_clos(conn):
    r = operations.saisir(conn, type="loyer", montant=780, periode="2026-01",
                          date_operation="2026-01-05", bien_id=1)
    fiscal.cloturer(conn, 2026)
    with pytest.raises(ValueError, match="clos"):
        operations.annuler(conn, r["operation_id"])


def test_double_annulation_refusee(conn):
    r = operations.saisir(conn, type="loyer", montant=780, periode="2026-01",
                          date_operation="2026-01-05", bien_id=1)
    operations.annuler(conn, r["operation_id"])
    with pytest.raises(ValueError, match="déjà annulée"):
        operations.annuler(conn, r["operation_id"])


def test_migration_palier_5(tmp_path):
    db = str(tmp_path / "v4.db")
    c = init_db.init_demo(db, FEC2025, 2026)
    c.execute("UPDATE meta SET valeur='4' WHERE cle='version_schema'")
    # simuler une base d'avant : retirer la colonne est impossible en SQLite,
    # on vérifie simplement que le palier est idempotent et marque v5
    c.commit()
    c.close()
    migrations.migrer(db)
    c = sqlite3.connect(db)
    assert init_db.version_base(c) == init_db.VERSION_SCHEMA
    c.execute("SELECT annulee FROM operation LIMIT 0")   # colonne présente
    c.close()


# === Sandrine : import bancaire en deux temps ==============================

def test_import_bancaire_bout_en_bout(client):
    cl, db = client
    csv = ("date;libelle;montant\n"
           "05/01/2026;VIR LOYER JANVIER DUPONT;780,00\n"
           "12/01/2026;PRLV EDF ELECTRICITE;-89,30\n")
    r = cl.post("/import/proposer",
                data={"releve": (io.BytesIO(csv.encode("cp1252")), "rel.csv")},
                content_type="multipart/form-data", follow_redirects=True)
    h = r.get_data(as_text=True)
    jeton = re.search(r'name="jeton" value="([0-9a-f]{32})"', h)
    assert jeton and h.count('name="ligne"') == 2
    r = cl.post("/import/valider",
                data={"jeton": jeton.group(1), "ligne": ["0"]},
                follow_redirects=True)
    assert "1 opération(s) enregistrée(s), 1 écartée(s)" in \
        r.get_data(as_text=True)
    cx = sqlite3.connect(db)
    assert cx.execute("SELECT COUNT(*) FROM operation").fetchone()[0] == 1
    cx.close()


def test_import_jeton_invalide(client):
    cl, _db = client
    r = cl.post("/import/valider", data={"jeton": "zzz", "ligne": ["0"]},
                follow_redirects=True)
    assert "expirée" in r.get_data(as_text=True)


# === Nadia : reprise d'un exercice depuis son FEC ==========================

def test_reprise_fec_depuis_l_interface(client):
    cl, db = client
    fec = open(FEC2025, "rb").read()
    r = cl.post("/exercice/reprendre-fec",
                data={"annee": "2025", "fec": (io.BytesIO(fec), "FEC.txt")},
                content_type="multipart/form-data", follow_redirects=True)
    h = r.get_data(as_text=True)
    assert "34 écritures rejouées" in h
    import reprise
    bal = reprise.lire_balance_fec(FEC2025)
    cx = sqlite3.connect(db)
    for compte, s in bal.items():
        interne = cx.execute(
            "SELECT COALESCE(ROUND(SUM(l.debit-l.credit),2),0) FROM ligne l "
            "JOIN ecriture e ON e.id=l.ecriture_id "
            "WHERE e.exercice_annee=2025 AND l.compte_num=?",
            (compte,)).fetchone()[0]
        assert interne == pytest.approx(round(s, 2), abs=0.005), compte
    cx.close()


def test_reprise_fec_refuse_exercice_existant(client):
    cl, _db = client
    fec = open(FEC2025, "rb").read()
    r = cl.post("/exercice/reprendre-fec",
                data={"annee": "2026", "fec": (io.BytesIO(fec), "FEC.txt")},
                content_type="multipart/form-data", follow_redirects=True)
    assert "existe déjà" in r.get_data(as_text=True)


# === Karim & Paul : frictions ==============================================

def test_doublon_double_clic_rattrape_par_les_controles(conn):
    for _ in range(2):
        operations.saisir(conn, type="loyer", montant=780, periode="2026-04",
                          date_operation="2026-04-05", bien_id=1)
    anomalies = controles.controler(conn, 2026)
    assert any("DOUBLON" in str(a.__dict__).upper() for a in anomalies)


def test_saisie_sans_bien_message_d_orientation(tmp_path):
    c = init_db.init(str(tmp_path / "vide.db"), "blanc", annee_cible=2026)
    with pytest.raises(ValueError, match="Immobilisations"):
        operations.saisir(c, type="loyer", montant=780, periode="2026-01",
                          date_operation="2026-01-05", bien_id=1)
    c.close()


def test_page_cloture_rassure_sur_la_reversibilite(client):
    cl, _db = client
    h = cl.get("/cloture").get_data(as_text=True)
    assert "irréversible" in h and "Dossiers" in h


# === Modèle de distribution : encart de soutien sur l'accueil ==============

def test_encart_don_sur_l_accueil(client):
    cl, _db = client
    h = cl.get("/", follow_redirects=True).get_data(as_text=True)
    assert "paypal.me/sfaure01" in h
    assert "sylvainfaure01@hotmail.fr" in h
    assert "facultatif" in h          # le ton : soutien, jamais un péage
    # l'encart ne s'invite pas sur les pages de travail « profondes »
    assert "paypal.me" not in cl.get("/cloture").get_data(as_text=True)
