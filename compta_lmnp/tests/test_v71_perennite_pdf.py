# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Tests v7.1 — J6 (sauvegardes + archivage FEC) et J7 (liasse PDF).
Lancer :  pytest -q tests/test_v71_perennite_pdf.py
"""
import importlib
import os
import sqlite3
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import init_db
import liasse
import perennite

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")


@pytest.fixture()
def dossier(tmp_path):
    """Base de démo dans un dossier jetable ; retourne (conn, db_path)."""
    db = str(tmp_path / "compta.db")
    conn = init_db.init_demo(db, FEC2025, 2026)
    yield conn, db
    conn.close()


# === J6 — sauvegardes ======================================================

def test_sauvegarde_cree_une_copie_ouvrable(dossier):
    conn, db = dossier
    chemin = perennite.sauvegarder(db, "test")
    assert chemin and os.path.exists(chemin)
    assert os.path.dirname(chemin).endswith("sauvegardes")
    # La copie est une base SQLite valide et complète.
    copie = sqlite3.connect(chemin)
    n_orig = conn.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0]
    n_copie = copie.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0]
    copie.close()
    assert n_copie == n_orig > 0


def test_sauvegarde_base_absente_ne_plante_pas(tmp_path):
    assert perennite.sauvegarder(str(tmp_path / "absente.db")) is None
    assert perennite.sauvegarde_quotidienne(str(tmp_path / "absente.db")) is None


def test_rotation_ne_garde_que_les_recentes(dossier, monkeypatch):
    _conn, db = dossier
    # Horodatages distincts forcés (la seconde près ne suffit pas en test).
    import perennite as p
    compteur = iter(range(100))

    class _FauxDatetime:
        @staticmethod
        def now():
            from datetime import datetime, timedelta
            return datetime(2026, 1, 1) + timedelta(seconds=next(compteur))
    monkeypatch.setattr(p, "datetime", _FauxDatetime)

    for _ in range(7):
        p.sauvegarder(db, "test", garder=3)
    restantes = p.lister_sauvegardes(db)
    assert len(restantes) == 3
    # Ce sont bien les plus récentes qui restent (tri décroissant).
    noms = [r["nom"] for r in restantes]
    assert noms == sorted(noms, reverse=True)


def test_sauvegarde_quotidienne_une_seule_fois_par_jour(dossier):
    _conn, db = dossier
    premiere = perennite.sauvegarde_quotidienne(db)
    seconde = perennite.sauvegarde_quotidienne(db)
    assert premiere is not None and seconde is None
    assert len(perennite.lister_sauvegardes(db)) == 1


# === J6 — archivage FEC + piste d'audit ====================================

def test_archivage_fec_manifeste_et_verification(dossier):
    conn, db = dossier
    arch = perennite.archiver_fec(conn, 2025, db)
    assert os.path.exists(arch["chemin"])
    assert len(arch["sha256"]) == 64
    # Le FEC archivé est identique octet à octet à un export direct.
    import export_fec
    direct = os.path.join(os.path.dirname(db), "direct.txt")
    export_fec.exporter(conn, 2025, direct)
    assert open(arch["chemin"], "rb").read() == open(direct, "rb").read()
    # Vérification d'intégrité : conforme.
    etats = perennite.verifier_archives(db)
    assert etats == [{"fichier": os.path.basename(arch["chemin"]),
                      "exercice": 2025, "statut": "ok"}]


def test_verification_detecte_alteration_et_disparition(dossier):
    conn, db = dossier
    a1 = perennite.archiver_fec(conn, 2025, db)
    a2 = perennite.archiver_fec(conn, 2025, db)
    # Altération d'un octet du premier, suppression du second.
    with open(a1["chemin"], "ab") as f:
        f.write(b"X")
    os.remove(a2["chemin"])
    statuts = {e["fichier"]: e["statut"] for e in perennite.verifier_archives(db)}
    assert statuts[os.path.basename(a1["chemin"])] == "modifie"
    assert statuts[os.path.basename(a2["chemin"])] == "absent"


# === J7 — liasse PDF =======================================================

def test_liasse_pdf_genere_un_pdf_valide(dossier, tmp_path):
    conn, _db = dossier
    liasse_pdf = importlib.import_module("liasse_pdf")
    L = liasse.generer(conn, 2026)
    chemin = str(tmp_path / "liasse.pdf")
    liasse_pdf.generer_pdf(L, chemin)
    contenu = open(chemin, "rb").read()
    assert contenu[:5] == b"%PDF-"
    assert contenu.rstrip().endswith(b"%%EOF")
    assert len(contenu) > 2000


# === Intégration web =======================================================

@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = str(tmp_path / "compta.db")
    init_db.init_demo(db, FEC2025, 2026).close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "bac.db"))
    import app as app_mod
    importlib.reload(app_mod)
    yield app_mod.app.test_client(), db
    monkeypatch.delenv("COMPTA_DB")
    monkeypatch.delenv("COMPTA_DB_BAC_A_SABLE")
    importlib.reload(app_mod)


def test_route_liasse_pdf(client):
    c, _db = client
    rep = c.get("/liasse.pdf?annee=2026")
    assert rep.status_code == 200
    assert rep.mimetype == "application/pdf"
    assert rep.data[:5] == b"%PDF-"
    assert "provisoire" in rep.headers["Content-Disposition"]


def test_cloture_web_sauvegarde_et_archive(client):
    c, db = client
    rep = c.post("/cloturer", data={"annee": "2026", "forcer": "1"},
                 follow_redirects=False)
    assert rep.status_code == 302
    # Une sauvegarde « avant-cloture » a été produite…
    noms = [s["nom"] for s in perennite.lister_sauvegardes(db)]
    assert any(n.endswith("-avant-cloture.db") for n in noms)
    # …et le FEC 2026 est archivé avec une empreinte conforme.
    etats = perennite.verifier_archives(db)
    assert etats and all(e["statut"] == "ok" for e in etats)
    assert etats[-1]["exercice"] == 2026


def test_version_affichee(client):
    c, _db = client
    rep = c.get("/liasse?annee=2026")
    assert b"Compta LMNP v" in rep.data
