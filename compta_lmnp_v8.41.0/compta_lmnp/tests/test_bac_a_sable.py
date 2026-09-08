# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Bac à sable : isolation du dossier réel, cycle de vie du cookie, audit complet.
"""
import os
import sqlite3
import sys
from datetime import date

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import pytest

import app as A
import audit_cycle
import operations


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Client Flask avec dossiers réel + sandbox redirigés vers tmp_path."""
    import init_db
    reel = str(tmp_path / "compta.db")
    sandbox = str(tmp_path / "bac_a_sable.db")
    init_db.init(reel, "blanc", annee_cible=date.today().year).close()
    monkeypatch.setattr(A, "DB", reel)
    monkeypatch.setattr(A, "BAC_A_SABLE_DB", sandbox)
    return A.app.test_client()


def _nb_ecritures(db):
    if not os.path.exists(db):
        return None
    return sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM ecriture").fetchone()[0]


def test_page_accessible(client):
    r = client.get("/bac-a-sable")
    assert r.status_code == 200
    assert "Bac à sable" in r.get_data(as_text=True)


def test_activation_pose_cookie_et_cree_la_base(client):
    r = client.post("/bac-a-sable/activer")
    assert any("dossier=bac_a_sable" in h
               for h in r.headers.getlist("Set-Cookie"))
    assert os.path.exists(A.BAC_A_SABLE_DB)


def test_bandeau_visible_dans_le_sandbox_seulement(client):
    client.post("/bac-a-sable/activer")
    assert "BAC À SABLE" in client.get("/saisie").get_data(as_text=True)
    client.post("/bac-a-sable/quitter")
    assert "BAC À SABLE" not in client.get("/saisie").get_data(as_text=True)


def test_isolation_du_dossier_reel(client):
    """Une saisie dans le sandbox ne modifie JAMAIS compta.db."""
    client.post("/bac-a-sable/activer")
    client.post("/bac-a-sable/reset", data={"mode": "blanc"})
    avant = _nb_ecritures(A.DB)

    conn = sqlite3.connect(A.BAC_A_SABLE_DB)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("INSERT INTO exploitant (nom,siren) VALUES ('Test','000000000')")
    conn.execute("INSERT INTO bien (exploitant_id,libelle) VALUES (1,'Bien test')")
    conn.commit()
    an = date.today().year
    operations.saisir(conn, type="loyer", montant=500.0,
                      date_operation=f"{an}-03-05", periode=f"{an}-03")
    conn.close()

    assert _nb_ecritures(A.BAC_A_SABLE_DB) >= 1
    assert _nb_ecritures(A.DB) == avant


def test_reset_efface_le_sandbox(client):
    client.post("/bac-a-sable/activer")
    conn = sqlite3.connect(A.BAC_A_SABLE_DB)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("INSERT INTO exploitant (nom,siren) VALUES ('X','1')")
    conn.commit()
    conn.close()
    client.post("/bac-a-sable/reset", data={"mode": "blanc"})
    n = sqlite3.connect(A.BAC_A_SABLE_DB).execute(
        "SELECT COUNT(*) FROM exploitant").fetchone()[0]
    assert n == 0


def test_audit_cycle_complet_conforme():
    """L'audit automatisé (22 vérifications, 3 phases) doit être 100 % PASS."""
    r = audit_cycle.executer()
    assert r.succes, "\n" + r.texte()
    phases = {c["phase"] for c in r.checks}
    assert any("nominal" in p for p in phases)
    assert any("anomalies" in p for p in phases)
    assert any("39 C" in p for p in phases)
