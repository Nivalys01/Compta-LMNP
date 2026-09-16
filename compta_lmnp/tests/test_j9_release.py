# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
J9 — cycle de release : migrations versionnées + paquet de distribution.
Lancer :  pytest -q tests/test_j9_release.py
"""
import os
import sqlite3
import sys
import zipfile

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import construire_distribution
import init_db
import migrations

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")


def _base_ancienne(tmp_path):
    """Simule une base d'AVANT le multi-biens/cession : on retire les
    structures récentes et la version."""
    db = str(tmp_path / "ancienne.db")
    init_db.init_demo(db, FEC2025, 2026).close()
    c = sqlite3.connect(db)
    c.execute("DROP TABLE IF EXISTS suivi_39c_bien")
    c.execute("DROP TABLE IF EXISTS meta")
    c.execute("DELETE FROM compte WHERE numero IN ('675000','775000')")
    c.commit()
    c.close()
    return db


def test_migration_base_ancienne(tmp_path):
    db = _base_ancienne(tmp_path)
    r = migrations.migrer(db)
    assert r["avant"] == 0
    assert r["apres"] == init_db.VERSION_SCHEMA
    assert r["sauvegarde"] and os.path.exists(r["sauvegarde"])   # copie AVANT
    c = sqlite3.connect(db)
    assert c.execute("SELECT 1 FROM sqlite_master WHERE name='suivi_39c_bien'"
                     ).fetchone()
    assert c.execute("SELECT 1 FROM compte WHERE numero='675000'").fetchone()
    assert init_db.version_base(c) == init_db.VERSION_SCHEMA
    c.close()


def test_migration_idempotente(tmp_path):
    db = _base_ancienne(tmp_path)
    migrations.migrer(db)
    r2 = migrations.migrer(db)                    # 2e passage : rien à faire
    assert r2["avant"] == r2["apres"] == init_db.VERSION_SCHEMA
    assert r2["sauvegarde"] is None               # pas de copie inutile


def test_migration_preserve_les_donnees(tmp_path):
    db = _base_ancienne(tmp_path)
    avant = sqlite3.connect(db).execute("SELECT COUNT(*) FROM ecriture"
                                        ).fetchone()[0]
    migrations.migrer(db)
    apres = sqlite3.connect(db).execute("SELECT COUNT(*) FROM ecriture"
                                        ).fetchone()[0]
    assert apres == avant                         # pas une écriture perdue


def test_paquet_client_sans_donnees_personnelles():
    cible = construire_distribution.construire()
    assert os.path.exists(cible)
    with zipfile.ZipFile(cible) as z:
        noms = z.namelist()
    assert not any(".db" in n for n in noms)
    assert not any("reference/" in n for n in noms)   # FEC réels exclus
    assert not any("tests/" in n for n in noms)
    assert any(n.endswith("app.py") for n in noms)
    assert any(n.endswith("LISEZ-MOI.md") for n in noms)
    assert any(n.endswith("migrations.py") for n in noms)


def test_garde_anti_fuite_bloque(tmp_path, monkeypatch):
    """Si un fichier interdit se glissait dans la liste, la construction
    doit ÉCHOUER (fuite bloquante, pas simplement évitée)."""
    fec = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")
    # DOCS porte désormais des couples (nom dans le paquet, chemin sur le
    # disque) : la licence est lue à la racine du dépôt et déposée sous un
    # autre nom dans le zip. Le fichier piégé garde son nom d'origine — c'est
    # bien ce nom-là que la garde doit reconnaître comme interdit.
    relatif = os.path.relpath(fec, HERE)
    monkeypatch.setattr(construire_distribution, "DOCS",
                        construire_distribution.DOCS + [(relatif, relatif)])
    with pytest.raises(SystemExit, match="FUITE"):
        construire_distribution.construire()


# === Défauts trouvés au test réel Linux (v8.0.1) ===========================

def test_paquet_contient_les_fichiers_utilises_par_les_lanceurs():
    """Défaut v8.0.0 : generer_certificat.* manquaient → HTTPS en panne sur
    une installation neuve."""
    cible = construire_distribution.construire()
    with zipfile.ZipFile(cible) as z:
        noms = {n.split("compta_lmnp/", 1)[-1] for n in z.namelist()}
    for attendu in ("generer_certificat.py", "generer_certificat.py",
                    "ouvrir_navigateur.py"):
        assert attendu in noms, f"{attendu} absent du paquet client"


def test_garde_paquet_incomplet_bloque(monkeypatch):
    """Retirer un fichier référencé par un lanceur doit FAIRE ÉCHOUER la
    construction, pas produire un paquet silencieusement cassé."""
    monkeypatch.setattr(
        construire_distribution, "LANCEURS",
        [f for f in construire_distribution.LANCEURS
         if f != "generer_certificat.py"])
    with pytest.raises(SystemExit, match="PAQUET INCOMPLET"):
        construire_distribution.construire()


def test_ouvrir_navigateur_rend_la_main_si_serveur_muet():
    """Sur un port mort, l'assistant abandonne proprement (il ne doit ni
    bloquer le lanceur ni ouvrir une page d'erreur)."""
    import ouvrir_navigateur
    assert ouvrir_navigateur.attendre_puis_ouvrir(
        "https://127.0.0.1:59999/", delai=1.5) is False


def test_lanceur_linux_affiche_toujours_l_adresse():
    """Les ouvreurs (xdg-open, webbrowser) renvoient « succès » même sans
    rien ouvrir : l'adresse doit être affichée dans tous les cas."""
    sh = open(os.path.join(HERE, "Compta-LMNP-Linux-macOS.sh"),
              encoding="utf-8").read()
    assert "adresse_en_grand" in sh
    # appelée sans condition avant le démarrage du serveur
    assert 'ok "Démarrage de Compta LMNP"' in sh
    assert sh.count("adresse_en_grand") >= 4       # définition + 3 appels


def test_lanceur_windows_ouvre_apres_le_serveur():
    """Défaut v8.0.0 : start "" "%URL%" s'exécutait AVANT app.py → page sur
    un port muet."""
    bat = open(os.path.join(HERE, "Compta-LMNP-Windows.bat"),
               encoding="utf-8", errors="ignore").read()
    assert 'ouvrir_navigateur.py' in bat
    assert 'start "" "%URL%"' not in bat           # l'ancien appel a disparu
