# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Cession d'un bien — sortie comptable, neutralisation fiscale, ligne G'.
Lancer :  pytest -q tests/test_cession.py
"""
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import cession
import export_fec
import fiscal
import init_db
import operations
import reprise

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")


@pytest.fixture()
def conn(tmp_path):
    c = init_db.init_demo(str(tmp_path / "c.db"), FEC2025, 2026)
    yield c
    c.close()


def test_cession_ecritures_et_equilibre(conn):
    r = cession.ceder_bien(conn, 1, "2026-07-10", 150000)
    assert r["dotation_complementaire"] > 0          # prorata janvier→juillet
    assert r["valeur_brute_sortie"] > 0
    assert r["pv_comptable"] == pytest.approx(150000 - r["vnc_sortie"])
    d, c = reprise.controle_equilibre(conn, 2026)
    assert abs(d - c) <= 0.005                       # partie double intacte
    # plus aucun composant actif ni immobilisation au bilan du bien
    actifs = conn.execute("SELECT COUNT(*) FROM composant WHERE bien_id=1 AND "
                          "(date_sortie IS NULL OR date_sortie='')").fetchone()[0]
    assert actifs == 0


def test_double_cession_refusee(conn):
    cession.ceder_bien(conn, 1, "2026-07-10", 150000)
    with pytest.raises(ValueError, match="déjà cédé"):
        cession.ceder_bien(conn, 1, "2026-08-01", 1)


def test_cloture_sans_double_dotation_et_pv_neutralisee(conn):
    for m in range(1, 8):
        operations.saisir(conn, type="loyer", montant=795,
                          date_operation=f"2026-{m:02d}-05", bien_id=1)
    r_ces = cession.ceder_bien(conn, 1, "2026-07-10", 150000)
    r = fiscal.cloturer(conn, 2026)
    ag = r["agregats"]
    # la clôture n'a PAS redoté les composants sortis
    assert ag["dotation"] == pytest.approx(r_ces["dotation_complementaire"], abs=0.02)
    # neutralisation : ni le produit 775 ni la VNC 675 ne teintent le fiscal
    assert ag["produits_cession"] == pytest.approx(150000)
    assert ag["vnc_cession"] == pytest.approx(r_ces["vnc_sortie"])
    attendu = round(ag["resultat_comptable"]
                    + r["suivi_39c"]["report_annee"]
                    - r["suivi_39c"]["utilisation_annee"]
                    + ag["vnc_cession"] - ag["produits_cession"], 2)
    assert r["resultat_fiscal"] == pytest.approx(attendu)
    # le prix de cession n'entre pas dans le plafond 39C (loyers acquis)
    assert r["suivi_39c"]["plafond_deductible"] < 100000


def test_ligne_g_prime_stock_39c_du_bien_cede_perdu(conn):
    # année 1 : constituer un stock 39C (loyers faibles)
    for m in range(1, 13):
        operations.saisir(conn, type="loyer", montant=300,
                          date_operation=f"2026-{m:02d}-05", bien_id=1)
    r1 = fiscal.cloturer(conn, 2026)
    stock = r1["suivi_39c"]["stock_cloture"]
    assert stock > 0
    # année 2 : cession du bien → le stock sort en G', le global tombe à zéro
    reprise.ouvrir_exercice(conn, 2027)
    cession.ceder_bien(conn, 1, "2027-03-31", 120000)
    r2 = fiscal.cloturer(conn, 2027)
    par_bien = {v["bien_id"]: v for v in fiscal.suivi_39c_par_bien(conn, 2027)}
    assert par_bien[1]["sortie_bien"] > 0            # ligne G' renseignée
    assert par_bien[1]["stock_cloture"] == pytest.approx(0.0)
    assert r2["suivi_39c"]["sorties_39c"] == pytest.approx(par_bien[1]["sortie_bien"])
    assert r2["suivi_39c"]["stock_cloture"] == pytest.approx(0.0)


def test_fec_conforme_apres_cession(conn, tmp_path):
    cession.ceder_bien(conn, 1, "2026-07-10", 150000)
    fiscal.cloturer(conn, 2026)
    fec = str(tmp_path / "FEC.txt")
    export_fec.exporter(conn, 2026, fec)
    v = subprocess.run([sys.executable, os.path.join(HERE, "valider_fec.py"),
                        fec], capture_output=True, text=True)
    assert v.returncode == 0, v.stdout + v.stderr
