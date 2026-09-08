# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Audit interne (fonctionnel + code) — défauts trouvés et corrigés.

1. Une base NEUVE était marquée « schéma 0 » : le démarrage annonçait une
   migration 0 → N et créait une copie « avant-migration » inutile.
2. La garde de version écrivait en base à CHAQUE affichage de page
   (transaction d'écriture inutile, contention possible avec une clôture)
   et pouvait marquer un dossier « à jour » sans qu'aucun palier n'ait
   tourné.
3. Le FEC archivé à chaque clôture n'était accessible NULLE PART depuis
   l'interface — or c'est le fichier réclamé lors d'un contrôle
   (art. L. 47 A-I du LPF).
4. Un dossier nommé CON, AUX, PRN, NUL, COM1-9 ou LPT1-9 produisait un slug
   impossible à créer sous Windows (noms de périphériques réservés).

Lancer :  pytest -q tests/test_audit_fonctionnel.py
"""
import importlib
import os
import re
import sqlite3
import sys
import time

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import dossiers as dossiers_mod
import init_db
import migrations

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = str(tmp_path / "compta.db")
    init_db.init_demo(db, FEC2025, 2026).close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "bac.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    yield app_mod.app.test_client(), db
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


# === 1. Base neuve déjà au niveau ==========================================

def test_base_neuve_marquee_a_la_version_courante(tmp_path):
    db = str(tmp_path / "neuve.db")
    init_db.init(db, "blanc", annee_cible=2026).close()
    c = sqlite3.connect(db)
    assert init_db.version_base(c) == init_db.VERSION_SCHEMA
    c.close()


def test_base_neuve_ne_declenche_aucune_migration(tmp_path):
    db = str(tmp_path / "neuve.db")
    init_db.init(db, "blanc", annee_cible=2026).close()
    r = migrations.migrer(db)
    assert r["avant"] == r["apres"] == init_db.VERSION_SCHEMA
    assert r["sauvegarde"] is None        # aucune copie « avant-migration »


# === 2. Consultation = lecture seule =======================================

def test_afficher_une_page_n_ecrit_pas_en_base(client):
    c, db = client
    for page in ("/saisie", "/cloture", "/reglementation", "/veille"):
        c.get(page)                       # 1er passage : créations légitimes
    time.sleep(0.02)
    avant = os.path.getmtime(db)
    time.sleep(0.05)
    for page in ("/saisie", "/cloture", "/reglementation", "/veille"):
        assert c.get(page).status_code == 200
    assert os.path.getmtime(db) == avant, \
        "consulter une page ne doit RIEN écrire en base"


def test_version_non_marquee_par_une_simple_consultation(tmp_path, monkeypatch):
    """Une base en retard de schéma est MIGRÉE à l'ouverture, jamais
    simplement marquée.

    L'exigence d'origine — « une base ne doit pas être déclarée à jour du
    seul fait qu'on l'affiche » — reste entière : ce qui a changé en
    v8.40.0, c'est qu'au lieu de laisser passer une base en retard, on la
    migre pour de bon. La revue de la couche web avait montré qu'une base
    ancienne ADOPTÉE en cours de session (le registre le prévoit
    explicitement) n'était jamais migrée : les routes écrivaient dans un
    schéma périmé, sans la copie de sûreté que la migration produit.

    Le test vérifie donc les deux : la version finale est celle du
    logiciel, ET les paliers ont réellement tourné — ce dont atteste la
    sauvegarde « avant-migration ».
    """
    db = str(tmp_path / "vieille.db")
    init_db.init_demo(db, FEC2025, 2026).close()
    cx = sqlite3.connect(db)
    cx.execute("DROP TABLE IF EXISTS meta")
    cx.commit()
    cx.close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "bac.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    app_mod.app.test_client().get("/saisie")
    cx = sqlite3.connect(db)
    assert init_db.version_base(cx) == init_db.VERSION_SCHEMA
    cx.close()
    import perennite
    sauvegardes = os.listdir(perennite.dossier_sauvegardes(db))
    assert any("avant-migration" in x for x in sauvegardes), sauvegardes
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


# === 3. Archives FEC accessibles ===========================================

def test_fec_archive_listable_et_telechargeable(client):
    c, _db = client
    c.post("/cloturer", data={"annee": "2026"})
    h = c.get("/archives").get_data(as_text=True)
    noms = re.findall(r'href="/archives/([^"]+)"', h)
    assert noms, "le FEC archivé doit apparaître dans la page Archives"
    r = c.get("/archives/" + noms[0])
    assert r.status_code == 200
    contenu = r.data.decode("utf-8", "replace")
    assert "JournalCode" in contenu       # c'est bien un FEC
    assert "\r\n" in contenu              # fins de ligne conformes


def test_archives_refuse_la_remontee_de_chemin(client):
    c, _db = client
    for tentative in ("..%2f..%2fcompta.db", "....//compta.db", "compta.db"):
        r = c.get("/archives/" + tentative)
        assert r.status_code in (302, 404)


# === 4. Noms réservés Windows ==============================================

@pytest.mark.parametrize("nom", ["CON", "aux", "PRN", "nul", "COM1", "LPT9"])
def test_nom_reserve_windows_refuse(nom):
    with pytest.raises(ValueError, match="réservé"):
        dossiers_mod.slugifier(nom)


def test_nom_normal_toujours_accepte():
    assert dossiers_mod.slugifier("Studio Nancy centre") == "studio-nancy-centre"
    assert dossiers_mod.slugifier("Conciergerie du Puy") == "conciergerie-du-puy"
