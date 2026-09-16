# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Audit pré-diffusion v7.2 — chaque défaut trouvé pendant l'audit devient un
test permanent (non-régression), complété de vérifications d'intégration
CROISÉE entre J6 (pérennité), J7 (PDF) et J8 (multi-dossiers).
Lancer :  pytest -q tests/test_audit_v72.py
"""
import importlib
import io
import os
import sqlite3
import subprocess
import sys

import conftest

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import dossiers
import init_db
import liasse
import perennite

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")


@pytest.fixture()
def conn_demo(tmp_path):
    c = init_db.init_demo(str(tmp_path / "d.db"), FEC2025, 2026)
    yield c
    c.close()


# === Défaut n°1 (audit) : balisage dans les données → crash PDF ============

def test_pdf_survit_aux_balises_dans_le_nom_exploitant(conn_demo):
    conn_demo.execute(
        "UPDATE exploitant SET nom = 'FAURE <b>& fils</b> <script>alert(1)'")
    conn_demo.commit()
    import liasse_pdf
    buf = io.BytesIO()
    liasse_pdf.generer_pdf(liasse.generer(conn_demo, 2026), buf)
    assert buf.getvalue()[:5] == b"%PDF-"


def test_pdf_survit_aux_libelles_de_composants_hostiles(conn_demo):
    conn_demo.execute(
        "UPDATE composant SET libelle = ? WHERE id = 1",
        ("Installation <générale> d'une description & interminable qui doit "
         "passer à la ligne au lieu de déborder ou de faire planter la "
         "génération du tableau 2033-C du document",))
    conn_demo.commit()
    import liasse_pdf
    buf = io.BytesIO()
    liasse_pdf.generer_pdf(liasse.generer(conn_demo, 2026), buf)
    assert buf.getvalue()[:5] == b"%PDF-"


# === Défaut n°2 (audit) : registre perdu → réinitialisation destructrice ===

def test_recreer_un_dossier_orphelin_conserve_les_donnees(tmp_path):
    racine = str(tmp_path)
    d = dossiers.creer(racine, "Important", annee_cible=2026)
    assert d["adopte"] is False
    con = sqlite3.connect(d["chemin"])
    con.execute("INSERT INTO exercice (annee, date_debut, date_fin, statut) "
                "VALUES (2031,'2031-01-01','2031-12-31','ouvert')")
    con.commit()
    con.close()

    os.remove(os.path.join(racine, "dossiers.json"))     # registre perdu
    d2 = dossiers.creer(racine, "Important", annee_cible=2026)
    assert d2["adopte"] is True                          # rattaché, pas recréé
    con = sqlite3.connect(d2["chemin"])
    assert con.execute("SELECT COUNT(*) FROM exercice WHERE annee=2031"
                       ).fetchone()[0] == 1              # données intactes
    con.close()


# === Défaut n°3 (audit) : sauvegarde de démarrage limitée au principal =====

def test_sauvegardes_quotidiennes_couvrent_tous_les_dossiers(tmp_path):
    racine = str(tmp_path)
    principal = str(tmp_path / "compta.db")
    init_db.init(principal, "blanc", annee_cible=2026).close()
    d = dossiers.creer(racine, "Studio Nancy", annee_cible=2026)

    chemins = [e["chemin"] for e in dossiers.lister(racine, principal)
               if e["existe"]]
    faites = perennite.sauvegardes_quotidiennes(chemins)
    assert len(faites) == 2                              # principal + studio
    assert perennite.lister_sauvegardes(principal)
    assert perennite.lister_sauvegardes(d["chemin"])
    # Chaque sauvegarde vit À CÔTÉ de sa base (tiroir par dossier).
    assert os.path.join("dossiers", "studio-nancy", "sauvegardes") in \
        perennite.lister_sauvegardes(d["chemin"])[0]["chemin"]
    # Second appel le même jour : aucun doublon.
    assert perennite.sauvegardes_quotidiennes(chemins) == []


# === Intégrations croisées J6 × J7 × J8 ====================================

@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = str(tmp_path / "compta.db")
    init_db.init_demo(db, FEC2025, 2026).close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "bac.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    yield app_mod.app.test_client(), app_mod, str(tmp_path)
    monkeypatch.delenv("COMPTA_DB")
    monkeypatch.delenv("COMPTA_DB_BAC_A_SABLE")
    importlib.reload(app_mod)


def test_fec_archive_passe_le_validateur_independant(client, tmp_path):
    """J6 × J3 : l'archive produite à la clôture doit être un FEC conforme."""
    c, _app_mod, racine = client
    c.post("/cloturer", data={"annee": "2026", "forcer": "1"})
    archives = perennite.dossier_archives(str(tmp_path / "compta.db"))
    fecs = [f for f in os.listdir(archives) if f.endswith(".txt")]
    assert fecs
    r = subprocess.run(
        [sys.executable, conftest.source("valider_fec.py"),
         os.path.join(archives, fecs[0])],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_cloture_dossier_secondaire_archive_dans_son_tiroir(client):
    """J8 × J6 : sauvegardes et archives d'un dossier secondaire restent
    chez lui — jamais mélangées avec celles du principal."""
    c, _app_mod, racine = client
    c.post("/dossiers/creer", data={"nom": "Studio Nancy"})
    # Un exercice vierge se clôture (dotation nulle) — on force au besoin.
    from datetime import date
    annee = date.today().year
    c.post("/cloturer", data={"annee": str(annee), "forcer": "1"})
    db_studio = os.path.join(racine, "dossiers", "studio-nancy", "compta.db")
    noms = [s["nom"] for s in perennite.lister_sauvegardes(db_studio)]
    assert any(n.endswith("-avant-cloture.db") for n in noms)
    etats = perennite.verifier_archives(db_studio)
    assert etats and etats[-1]["exercice"] == annee
    # Rien n'a fui vers le principal.
    assert perennite.verifier_archives(os.path.join(racine, "compta.db")) == []


def test_pdf_liasse_depuis_un_dossier_secondaire(client):
    """J8 × J7 : le PDF se génère depuis n'importe quel dossier actif."""
    c, _app_mod, _racine = client
    c.post("/dossiers/creer", data={"nom": "Studio Nancy"})
    from datetime import date
    rep = c.get(f"/liasse.pdf?annee={date.today().year}")
    assert rep.status_code == 200 and rep.data[:5] == b"%PDF-"


def test_creer_dossier_depuis_le_bac_a_sable_en_sort_explicitement(client):
    """J8 × bac à sable : créer un dossier réel depuis le bac à sable ouvre
    ce dossier (sortie du bac assumée et affichée), sans mémo caduc."""
    c, _app_mod, _racine = client
    c.post("/bac-a-sable/activer")
    c.post("/dossiers/creer", data={"nom": "Studio Nancy"})
    page = c.get("/saisie").get_data(as_text=True)
    assert "BAC À SABLE" not in page
    entete = page.split("<main")[0]
    assert "Studio Nancy" in entete
