# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Audit de rapprochement guichet ↔ validateur FEC — conformité par construction.

Principe : toute écriture acceptée par le guichet unique (ecritures.inserer)
doit produire un FEC conforme (valider_fec.valider). Chaque brèche trouvée
lors de l'audit devient un test permanent, plus un test « propriété » qui
génère des écritures hostiles et vérifie l'invariant : accepté ⇒ FEC conforme.

Lancer :  pytest -q tests/test_rapprochement_fec.py
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import ecritures
import export_fec
import init_db
import valider_fec

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")
B, P = "108000", "708810"          # contrepartie exploitant / loyers


@pytest.fixture()
def conn(tmp_path):
    c = init_db.init_demo(str(tmp_path / "d.db"), FEC2025, 2026)
    yield c
    c.close()


def _ins(conn, **kw):
    return ecritures.inserer(conn, journal="OD", annee=2026, commit=False, **kw)


# === Brèches trouvées à l'audit → rejet au guichet =========================

def test_libelle_vide_rejete(conn):
    with pytest.raises(ValueError, match="libellé.*obligatoire"):
        _ins(conn, date="2026-05-01", libelle="",
             lignes=[(B, 100, 0), (P, 0, 100)])


def test_libelle_espaces_rejete(conn):
    with pytest.raises(ValueError, match="libellé.*obligatoire"):
        _ins(conn, date="2026-05-01", libelle="   ",
             lignes=[(B, 100, 0), (P, 0, 100)])


def test_piece_ref_vide_rejetee(conn):
    with pytest.raises(ValueError, match="pièce.*obligatoire"):
        _ins(conn, date="2026-05-01", libelle="loyer", piece_ref="",
             lignes=[(B, 100, 0), (P, 0, 100)])


def test_date_hors_exercice_rejetee(conn):
    with pytest.raises(ValueError, match="hors de l'exercice"):
        _ins(conn, date="2027-05-01", libelle="loyer",
             lignes=[(B, 100, 0), (P, 0, 100)])


def test_date_malformee_rejetee(conn):
    with pytest.raises(ValueError, match="[Dd]ate.*invalide"):
        _ins(conn, date="pas-une-date", libelle="loyer",
             lignes=[(B, 100, 0), (P, 0, 100)])


def test_une_seule_ligne_rejetee(conn):
    with pytest.raises(ValueError, match="au moins deux lignes"):
        _ins(conn, date="2026-05-01", libelle="x", verifier_equilibre=False,
             lignes=[(B, 0, 0)])


@pytest.mark.parametrize("mauvais", ["loyer\tmars", "loyer\nmars", "loyer\rmars"])
def test_caractere_de_structure_dans_libelle_rejete(conn, mauvais):
    with pytest.raises(ValueError, match="caractère interdit"):
        _ins(conn, date="2026-05-01", libelle=mauvais,
             lignes=[(B, 100, 0), (P, 0, 100)])


def test_tabulation_dans_piece_ref_rejetee(conn):
    with pytest.raises(ValueError, match="caractère interdit"):
        _ins(conn, date="2026-05-01", libelle="loyer", piece_ref="P\t1",
             lignes=[(B, 100, 0), (P, 0, 100)])


def test_tabulation_dans_libelle_de_ligne_rejetee(conn):
    with pytest.raises(ValueError, match="caractère interdit"):
        _ins(conn, date="2026-05-01", libelle="ok",
             lignes=[(B, 100, 0, "lib\tx"), (P, 0, 100, "ok")])


# === L'écriture normale passe toujours (pas de faux positif) ===============

def test_ecriture_normale_acceptee(conn):
    r = _ins(conn, date="2026-05-01", libelle="Loyer mai", piece_ref="2026-05",
             lignes=[(B, 795, 0), (P, 0, 795)])
    conn.commit()
    assert r["ecriture_num"] > 0


# === Symétrie du validateur : il détecte aussi la date hors exercice =======

def test_validateur_detecte_date_hors_exercice(conn, tmp_path):
    # On force l'insertion (garde désactivée) pour fabriquer un FEC vicié,
    # puis on vérifie que le validateur, lui, l'attrape — les deux côtés du
    # rapprochement sont symétriques.
    _ins(conn, date="2027-05-01", libelle="loyer", piece_ref="X",
         lignes=[(B, 100, 0), (P, 0, 100)], verifier_conformite=False)
    conn.commit()
    fec = str(tmp_path / "vicie.txt")
    export_fec.exporter(conn, 2026, fec)
    errs = valider_fec.valider(fec)
    assert any("hors de l'exercice" in e for e in errs)


# === Test « propriété » : accepté au guichet ⇒ FEC conforme ================

@pytest.mark.parametrize("libelle,piece,date,lignes", [
    ("Loyer normal", "P1", "2026-01-15", [(B, 795, 0), (P, 0, 795)]),
    ("Charge & Cie <SARL>", "F-2026/03", "2026-03-31",
     [("614100", 120.50, 0), (B, 0, 120.50)]),
    ("Écriture à 3 lignes", "P2", "2026-06-30",
     [(B, 300, 0), (P, 0, 200), ("628800", 0, 100)]),
    ("Montant avec centimes", "P3", "2026-12-31",
     [(B, 0, 1234.56), ("628800", 1234.56, 0)]),
])
def test_propriete_accepte_implique_conforme(conn, tmp_path, libelle, piece,
                                             date, lignes):
    """Invariant central : si le guichet accepte, le FEC est conforme."""
    try:
        _ins(conn, date=date, libelle=libelle, piece_ref=piece, lignes=lignes)
        conn.commit()
    except ValueError:
        pytest.skip("écriture rejetée au guichet — hors périmètre du test")
    fec = str(tmp_path / "prop.txt")
    export_fec.exporter(conn, 2026, fec)
    assert valider_fec.valider(fec) == []


def test_fuzz_aucune_ecriture_acceptee_ne_casse_le_fec(conn, tmp_path):
    """Fuzz ciblé : on bombarde le guichet de libellés/pièces hostiles ; pour
    chaque écriture ACCEPTÉE, le FEC exporté doit rester conforme."""
    import random
    random.seed(2026)
    hostiles = ["", "   ", "ok", "a\tb", "a\nb", "a\rb", "é&<>\"'", "x" * 200,
                "café", "P\t2", "normal"]
    acceptees = 0
    for i in range(60):
        lib = random.choice(hostiles)
        piece = random.choice(hostiles)
        jour = random.randint(1, 28)
        try:
            _ins(conn, date=f"2026-{random.randint(1,12):02d}-{jour:02d}",
                 libelle=lib, piece_ref=piece,
                 lignes=[(B, 100, 0), (P, 0, 100)])
            conn.commit()
            acceptees += 1
        except ValueError:
            conn.rollback()
    fec = str(tmp_path / "fuzz.txt")
    export_fec.exporter(conn, 2026, fec)
    erreurs = valider_fec.valider(fec)
    assert erreurs == [], f"{acceptees} acceptées, FEC vicié : {erreurs[:3]}"
