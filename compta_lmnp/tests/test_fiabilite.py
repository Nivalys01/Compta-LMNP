# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Revue de fiabilité (campagnes R1-R6) figée en non-régression.

Failles corrigées par cette campagne :
  1. aucune fonction de restauration n'existait (sauvegarde sans plan de
     retour) → perennite.restaurer(), avec vérification d'intégrité de la
     sauvegarde AVANT écrasement et copie de sûreté réversible ;
  2. RÉGRESSION v7.2.2 : le RELEASE d'un savepoint le plus externe vaut
     COMMIT en SQLite → inserer(commit=False) commitait en douce, brisant
     l'atomicité de la clôture face à une coupure de courant ;
  3. deux saisies simultanées pouvaient entrer en collision de numéro
     d'écriture → rejeu borné quand le numéro est auto-attribué ;
  4. import bancaire : crash sur CSV Windows (cp1252) ou binaire, perte
     SILENCIEUSE des montants à espace insécable (1 234,56).

Lancer :  pytest -q tests/test_fiabilite.py
"""
import os
import sqlite3
import subprocess
import sys
import threading

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import ecritures
import fiscal
import import_bancaire
import init_db
import operations
import perennite
import reprise

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")


@pytest.fixture()
def db(tmp_path):
    chemin = str(tmp_path / "compta.db")
    init_db.init_demo(chemin, FEC2025, 2026).close()
    return chemin


# === R1 : exercice de restauration =========================================

def test_restauration_apres_corruption(db):
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    operations.saisir(conn, type="loyer", montant=795.50,
                      date_operation="2026-02-05", bien_id=1)
    n_avant = conn.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0]
    conn.close()
    sv = perennite.sauvegarder(db, "test")
    with open(db, "r+b") as f:                 # saccage le fichier
        f.seek(100)
        f.write(b"\x00" * 4096)
    surete = perennite.restaurer(db, sv)
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert conn.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0] == n_avant
    conn.close()
    assert surete and os.path.exists(surete)   # l'état corrompu est conservé


def test_restauration_refuse_une_sauvegarde_corrompue(db):
    sv = perennite.sauvegarder(db, "saine")
    with open(sv, "r+b") as f:
        f.seek(50)
        f.write(b"\xff" * 2048)
    with pytest.raises(ValueError):
        perennite.restaurer(db, sv)


# === R2 : atomicité face au crash ==========================================

def test_inserer_commit_false_ne_commite_pas(db):
    """Régression v7.2.2 : RELEASE du savepoint le plus externe = COMMIT.
    Le contrat commit=False doit laisser la transaction OUVERTE."""
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    ecritures.inserer(conn, journal="OD", annee=2026, date="2026-06-01",
                      libelle="atomicite", commit=False,
                      lignes=[("108000", 1, 0), ("708810", 0, 1)])
    assert conn.in_transaction               # rien n'est commité
    autre = sqlite3.connect(db)              # invisible d'une autre connexion
    n = autre.execute("SELECT COUNT(*) FROM ecriture "
                      "WHERE libelle='atomicite'").fetchone()[0]
    assert n == 0
    autre.close()
    conn.rollback()
    conn.close()


def test_crash_en_pleine_cloture_ne_laisse_rien(db):
    """kill -9 pendant la clôture (coupure de courant simulée) :
    à la réouverture, ni dotation fantôme ni exercice à moitié clos."""
    script = f'''
import os, sys
# modules/ en plus de la racine : les modules métier y sont regroupés.
sys.path.insert(0, {HERE!r})
sys.path.insert(0, os.path.join({HERE!r}, "modules"))
import sqlite3, fiscal, amortissement
conn = sqlite3.connect({db!r})
conn.execute("PRAGMA foreign_keys = ON")
_orig = amortissement.generer_cloture
def piege(conn, annee, commit=False):
    _orig(conn, annee, commit=False)
    os.kill(os.getpid(), 9)
amortissement.generer_cloture = piege
fiscal.cloturer(conn, 2026)
'''
    r = subprocess.run([sys.executable, "-c", script], capture_output=True)
    assert r.returncode == -9
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert conn.execute("SELECT statut FROM exercice "
                        "WHERE annee=2026").fetchone()[0] == "ouvert"
    assert conn.execute("SELECT COUNT(*) FROM ecriture "
                        "WHERE libelle LIKE '%otation%'").fetchone()[0] == 0
    conn.close()


# === R3 : concurrence ======================================================

def test_saisies_simultanees_sans_collision(db):
    erreurs = []

    def marteau(t):
        for i in range(10):
            c = sqlite3.connect(db, timeout=10)
            c.execute("PRAGMA foreign_keys = ON")
            try:
                operations.saisir(c, type="loyer", montant=100 + t,
                                  date_operation=f"2026-{(i % 12) + 1:02d}-10",
                                  bien_id=1)
            except Exception as e:            # noqa: BLE001 — bilan du test
                erreurs.append(str(e))
            finally:
                c.close()

    fils = [threading.Thread(target=marteau, args=(t,)) for t in range(4)]
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    assert erreurs == []
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM operation "
                     "WHERE exercice_annee=2026").fetchone()[0]
    d, c = reprise.controle_equilibre(conn, 2026)
    nums = [r[0] for r in conn.execute(
        "SELECT ecriture_num FROM ecriture WHERE exercice_annee=2026 ORDER BY 1")]
    conn.close()
    # 4 fils × 10 saisies. On compte l'exercice COURANT uniquement : le
    # dossier de démonstration porte désormais un exercice précédent déjà
    # garni, qui n'a rien à voir avec ce que ce test mesure.
    assert n == 40
    assert abs(d - c) <= 0.005
    assert nums == list(range(nums[0], nums[-1] + 1))   # numérotation dense


def test_double_clic_cloture_une_seule_dotation(db):
    resultats = []

    def clore():
        c = sqlite3.connect(db, timeout=10)
        c.execute("PRAGMA foreign_keys = ON")
        try:
            fiscal.cloturer(c, 2026)
            resultats.append("ok")
        except (ValueError, sqlite3.OperationalError):
            resultats.append("refus")
        finally:
            c.close()

    t1, t2 = threading.Thread(target=clore), threading.Thread(target=clore)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert sorted(resultats) == ["ok", "refus"]
    conn = sqlite3.connect(db)
    dot = conn.execute("SELECT COUNT(*) FROM ecriture WHERE libelle LIKE "
                       "'%otation%' AND exercice_annee=2026").fetchone()[0]
    conn.close()
    assert dot == 1


# === R4 : import bancaire hostile ==========================================

def _releve(tmp_path, contenu, binaire=False, encodage="utf-8"):
    p = str(tmp_path / "releve.csv")
    if binaire:
        open(p, "wb").write(contenu)
    else:
        open(p, "w", encoding=encodage).write(contenu)
    return p


def test_import_cp1252_accents_intacts(db, tmp_path):
    conn = sqlite3.connect(db)
    p = _releve(tmp_path, "date;libelle;montant\n"
                "05/02/2026;VIR LOYER F\xe9vrier;795,50\n", encodage="cp1252")
    props = import_bancaire.proposer(p, conn)
    conn.close()
    assert len(props) == 1
    assert props[0]["libelle"] == "VIR LOYER Février"


def test_import_montant_espace_insecable_pas_de_perte(db, tmp_path):
    """1\u202f234,56 était ignoré EN SILENCE — perte de données invisible."""
    conn = sqlite3.connect(db)
    p = _releve(tmp_path, "date;libelle;montant\n"
                "05/02/2026;GROS VIR;1\u202f234,56\n")
    props = import_bancaire.proposer(p, conn)
    conn.close()
    assert len(props) == 1
    assert props[0]["montant"] == 1234.56


def test_import_binaire_refus_propre(db, tmp_path):
    conn = sqlite3.connect(db)
    p = _releve(tmp_path, b"%PDF-1.4\x00\x01\xff\xfe", binaire=True)
    with pytest.raises(ValueError, match="CSV"):
        import_bancaire.proposer(p, conn)
    conn.close()


def test_import_libelle_avec_tab_assaini(db, tmp_path):
    """Un libellé bancaire avec tabulation doit être importable (sinon le
    guichet le rejetterait en plein milieu d'import)."""
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    p = _releve(tmp_path, 'date;libelle;montant\n'
                '05/02/2026;"LOYER\tDUPONT\nmars";795,50\n')
    props = import_bancaire.importer(conn, p, valider=True)
    conn.close()
    assert props[0]["libelle"] == "LOYER DUPONT mars"


# === R6 : dates bissextiles ================================================

def test_29_fevrier_bissextile_vs_inexistant(db):
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    fiscal.cloturer(conn, 2026)
    reprise.ouvrir_exercice(conn, 2027)
    fiscal.cloturer(conn, 2027)
    reprise.ouvrir_exercice(conn, 2028)
    operations.saisir(conn, type="loyer", montant=100,
                      date_operation="2028-02-29", exercice=2028, bien_id=1)
    with pytest.raises(ValueError):
        operations.saisir(conn, type="loyer", montant=100,
                          date_operation="2029-02-29", exercice=2028, bien_id=1)
    conn.close()
