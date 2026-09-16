# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Non-régression de l'audit v7 — verrouille quatre corrections :

  1. Export FEC : plus de contamination inter-exercices (la numérotation
     redémarrant à 1 chaque année, l'ancien filtre par EcritureNum mélangeait
     les exercices dès qu'il y en avait plusieurs en base).
  2. Clôture idempotente : un re-POST ne duplique ni la dotation DAA ni
     l'imputation des déficits.
  3. Saisie robuste : montants NaN/inf et dates malformées rejetés à l'entrée
     (ils traversaient les comparaisons et finissaient dans le FEC).
  4. Flashes échappés : plus d'injection HTML via ?ok= / ?err= / ?warn=.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fiscal
import init_db
import operations
import export_fec


@pytest.fixture
def conn(tmp_path):
    c = init_db.init(str(tmp_path / "t.db"), "blanc", annee_cible=2025)
    c.execute("INSERT INTO exploitant (id,nom,siren) VALUES (1,'TEST','000000000')")
    c.execute("INSERT INTO bien (id,exploitant_id,libelle) VALUES (1,1,'Appartement')")
    c.commit()
    yield c
    c.close()


def _ouvrir(conn, annee):
    conn.execute("INSERT INTO exercice (annee, date_debut, date_fin) "
                 "VALUES (?,?,?)", (annee, f"{annee}-01-01", f"{annee}-12-31"))
    conn.commit()


# ── 1. Export FEC multi-exercices ────────────────────────────────────────────

def test_export_fec_sans_contamination_inter_exercices(conn, tmp_path):
    import reprise
    operations.saisir(conn, type="loyer", montant=800.0,
                      date_operation="2025-03-05", periode="2025-03")
    operations.saisir(conn, type="loyer", montant=800.0,
                      date_operation="2025-04-05", periode="2025-04")
    fiscal.cloturer(conn, 2025)
    _ouvrir(conn, 2026)
    reprise.construire_an_interne(conn, 2026)
    operations.saisir(conn, type="loyer", montant=850.0,
                      date_operation="2026-03-05", periode="2026-03")

    p = export_fec.exporter(conn, 2026, str(tmp_path / "fec2026.txt"))
    lignes = open(p).read().splitlines()[1:]
    assert lignes, "FEC 2026 vide"
    annees = {lg.split("\t")[3][:4] for lg in lignes}
    assert annees == {"2026"}, f"exercices étrangers dans le FEC 2026 : {annees}"

    # L'export 2025 reste lui aussi pur.
    p25 = export_fec.exporter(conn, 2025, str(tmp_path / "fec2025.txt"))
    annees25 = {lg.split("\t")[3][:4] for lg in open(p25).read().splitlines()[1:]}
    assert annees25 == {"2025"}


# ── 2. Clôture idempotente et dotation unique ────────────────────────────────

def test_double_cloture_refusee_et_dotation_unique(conn):
    conn.execute("INSERT INTO composant (bien_id,libelle,valeur_brute,duree_annees,"
                 "date_mise_service,compte_immo,compte_amort) "
                 "VALUES (1,'Bâtiment',100000,25,'2025-01-01','213150','281315')")
    conn.commit()
    operations.saisir(conn, type="loyer", montant=800.0,
                      date_operation="2025-03-05", periode="2025-03")
    fiscal.cloturer(conn, 2025)

    with pytest.raises(ValueError, match="déjà clos"):
        fiscal.cloturer(conn, 2025)

    daa = conn.execute("SELECT COUNT(*) FROM ecriture WHERE exercice_annee=2025 "
                       "AND piece_ref='DAA'").fetchone()[0]
    assert daa == 1
    dot = conn.execute("SELECT SUM(l.debit) FROM ligne l "
                       "JOIN ecriture e ON e.id=l.ecriture_id "
                       "WHERE e.exercice_annee=2025 AND l.compte_num='681120'"
                       ).fetchone()[0]
    assert abs(dot - 4000.0) < 0.005


def test_dotation_directe_refusee_si_deja_generee(conn):
    import amortissement
    conn.execute("INSERT INTO composant (bien_id,libelle,valeur_brute,duree_annees,"
                 "date_mise_service,compte_immo,compte_amort) "
                 "VALUES (1,'Mobilier',5000,5,'2025-01-01','218400','281840')")
    conn.commit()
    amortissement.generer_cloture(conn, 2025)
    with pytest.raises(ValueError, match="déjà générée"):
        amortissement.generer_cloture(conn, 2025)


def test_cloture_exercice_inexistant_refusee(conn):
    with pytest.raises(ValueError, match="inexistant"):
        fiscal.cloturer(conn, 2099)


# ── 3. Validation des saisies ────────────────────────────────────────────────

@pytest.mark.parametrize("montant", [float("nan"), float("inf"), float("-inf")])
def test_montant_non_fini_rejete(conn, montant):
    with pytest.raises(ValueError):
        operations.saisir(conn, type="loyer", montant=montant,
                          date_operation="2025-03-05", periode="2025-03")
    n = conn.execute("SELECT COUNT(*) FROM ecriture WHERE exercice_annee=2025"
                     ).fetchone()[0]
    assert n == 0, "une écriture corrompue a été insérée"


def test_montant_non_fini_rejete_au_niveau_central(conn):
    import ecritures
    with pytest.raises(ValueError, match="non fini"):
        ecritures.inserer(conn, journal="OD", date="2025-06-01", annee=2025,
                          libelle="test", verifier_equilibre=False,
                          lignes=[("108000", float("nan"), 0.0),
                                  ("706000", 0.0, float("nan"))])


@pytest.mark.parametrize("mauvaise_date", ["2025-13-05", "2025-02-30",
                                           "05/03/2025", "n'importe quoi"])
def test_date_malformee_rejetee(conn, mauvaise_date):
    with pytest.raises(ValueError, match="Date d'opération invalide"):
        operations.saisir(conn, type="loyer", montant=800.0,
                          date_operation=mauvaise_date, periode="2025-03")


# ── 4. Échappement des flashes (XSS réfléchie) ───────────────────────────────

def test_flash_query_string_echappe(tmp_path, monkeypatch):
    db = str(tmp_path / "compta.db")
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "bac.db"))
    init_db.init(db, "blanc", annee_cible=2025).close()
    # app lit ses chemins à l'import : rechargement pour prendre les env.
    import importlib
    import app as app_mod
    importlib.reload(app_mod)
    client = app_mod.app.test_client()
    charge = "<script>alert(1)</script>"
    r = client.get(f"/saisie?ok={charge}&err={charge}&warn={charge}")
    html = r.get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
