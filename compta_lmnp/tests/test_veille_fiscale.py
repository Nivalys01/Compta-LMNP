# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Veille fiscale — corpus légal, prompt et rappel à l'ouverture d'exercice.
Lancer :  pytest -q tests/test_veille_fiscale.py
"""
import datetime
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import init_db
import pense_bete
import veille_fiscale

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")


@pytest.fixture()
def conn(tmp_path):
    c = init_db.init_demo(str(tmp_path / "v.db"), FEC2025, 2026)
    yield c
    c.close()


def test_corpus_couvre_les_textes_structurants():
    """Les textes que le MOTEUR applique doivent tous figurer au corpus."""
    refs = " ".join(r for r, *_ in veille_fiscale.CORPUS)
    for attendu in ("39 C", "156, I-1° ter", "155, IV", "50-0", "150 U",
                    "150 VB", "53 A", "L. 47 A-I", "261 D", "1447"):
        assert attendu in refs, f"texte absent du corpus : {attendu}"


def test_corpus_rattache_chaque_texte_a_un_effet():
    for ref, intitule, effet, _regle in veille_fiscale.CORPUS:
        assert ref and intitule and len(effet) > 40


def test_regles_liees_existent_vraiment():
    """Une règle citée par le corpus doit exister dans parametres."""
    import parametres
    connues = {cle for cle, *_ in parametres.REGLES_DEFAUT}
    for _ref, _int, _effet, regle in veille_fiscale.CORPUS:
        if regle:
            assert regle in connues, f"règle inconnue : {regle}"


def test_prompt_contient_annee_textes_et_garde_fous():
    p = veille_fiscale.prompt_veille(2027, "2026-01-01")
    assert "2027" in p and "2026-01-01" in p
    assert "39 C" in p and "150 VB" in p
    # garde-fous anti-hallucination et sources officielles
    assert "Légifrance" in p and "BOFiP" in p
    assert "ADOPTÉ" in p
    assert "N'invente" in p


def test_enregistrement_et_fraicheur_de_la_veille(conn):
    assert veille_fiscale.veille_a_refaire(conn) is True   # jamais faite
    veille_fiscale.enregistrer_veille(conn, "2026-06-01")
    assert veille_fiscale.derniere_veille(conn) == "2026-06-01"
    assert veille_fiscale.veille_a_refaire(
        conn, datetime.date(2026, 9, 1)) is False
    # au-delà de ~11 mois, il faut la refaire (une loi de finances par an)
    assert veille_fiscale.veille_a_refaire(
        conn, datetime.date(2027, 6, 1)) is True


def test_veille_vieillissante_rappelee_par_le_pense_bete(conn):
    veille_fiscale.enregistrer_veille(conn, "2025-01-01")
    titres = " | ".join(r["titre"] for r in
                        pense_bete.rappels(conn, datetime.date(2026, 6, 1)))
    assert "Veille fiscale" in titres


def test_veille_recente_pas_de_rappel(conn):
    veille_fiscale.enregistrer_veille(conn, "2026-05-01")
    titres = " | ".join(r["titre"] for r in
                        pense_bete.rappels(conn, datetime.date(2026, 6, 1)))
    assert "Veille fiscale" not in titres
