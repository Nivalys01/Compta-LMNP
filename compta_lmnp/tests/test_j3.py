# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Tests J3 — sérialiseur + validateur FEC.
Lancer :  pytest -q
"""
import os
import pytest

import init_db
import export_fec
import valider_fec as v

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REF = os.path.join(ROOT, "reference")
FEC2025 = os.path.join(REF, "FEC_REFERENCE_2025.txt")

EN_TETE = "\t".join(v.COLONNES)

# FEC minimal valide (1 écriture équilibrée, 2 lignes) servant de base aux mutations.
LIGNES_OK = [
    ["BQ","Banque","1","20260115","708810","Loyers et autres produits","","","NA","20260115","Loyer janvier","","795","","","20260115","",""],
    ["BQ","Banque","1","20260115","108000","Exploitant","","","NA","20260115","Loyer janvier","795","","","","20260115","",""],
]


def ecrire(tmp_path, lignes, en_tete=EN_TETE):
    p = tmp_path / "fec.txt"
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(en_tete + "\r\n")
        for lg in lignes:
            f.write("\t".join(lg) + "\r\n")
    return str(p)


# --- Sérialiseur -----------------------------------------------------------

@pytest.mark.parametrize("entree,attendu", [
    (0, ""), (0.0, ""), (8599.5, "8599,5"), (58500.0, "58500"),
    (0.10, "0,1"), (119528.15, "119528,15"), (949.37, "949,37"), (0.005, "0,01"),
])
def test_serialiser_montant(entree, attendu):
    assert export_fec.serialiser_montant(entree) == attendu


# --- Aller-retour : export d'un exercice -> validateur ---------------------

def test_export_an_2026_est_conforme(tmp_path):
    conn = init_db.init_demo(str(tmp_path / "t.db"), FEC2025, 2026)
    sortie = export_fec.exporter(conn, 2026, str(tmp_path / "FEC2026.txt"))
    conn.close()
    assert v.valider(sortie) == []


def test_export_format_physique(tmp_path):
    conn = init_db.init_demo(str(tmp_path / "t.db"), FEC2025, 2026)
    sortie = export_fec.exporter(conn, 2026, str(tmp_path / "FEC2026.txt"))
    conn.close()
    brut = open(sortie, "rb").read()
    assert brut.startswith(EN_TETE.encode())   # en-tête exact
    assert brut.endswith(b"\r\n")               # CRLF en fin de fichier
    premiere_data = brut.split(b"\r\n")[1]
    assert b";" not in premiere_data            # séparateur = tabulation, pas ';'
    assert b"\t" in premiere_data
    # Réimport par le validateur : l'export est auto-cohérent.
    assert v.valider(sortie) == []


# --- Les 3 FEC réels passent -----------------------------------------------

@pytest.mark.parametrize("annee", [2023, 2024, 2025])
def test_fec_reels_conformes(annee):
    chemin = os.path.join(REF, f"FEC_REFERENCE_{annee}.txt")
    assert v.valider(chemin) == []


# --- Batterie de FEC volontairement cassés (doivent être REJETÉS) ----------

def test_rejet_desequilibre_un_centime(tmp_path):
    lg = [row[:] for row in LIGNES_OK]
    lg[0][12] = "795,01"   # crédit 795,01 vs débit 795,00
    errs = v.valider(ecrire(tmp_path, lg))
    assert any("déséquilibrée" in e for e in errs)

def test_rejet_date_malformee(tmp_path):
    lg = [row[:] for row in LIGNES_OK]
    lg[0][3] = "2026-01-15"   # tiret au lieu de AAAAMMJJ
    errs = v.valider(ecrire(tmp_path, lg))
    assert any("EcritureDate" in e for e in errs)

def test_rejet_separateur_decimal_point(tmp_path):
    lg = [row[:] for row in LIGNES_OK]
    lg[0][12] = "795.00"
    lg[1][11] = "795.00"
    errs = v.valider(ecrire(tmp_path, lg))
    assert any("'.'" in e for e in errs)

def test_rejet_separateur_milliers(tmp_path):
    lg = [row[:] for row in LIGNES_OK]
    lg[0][12] = "1 795"
    lg[1][11] = "1 795"
    errs = v.valider(ecrire(tmp_path, lg))
    assert any("milliers" in e for e in errs)

def test_rejet_debit_et_credit_simultanes(tmp_path):
    lg = [row[:] for row in LIGNES_OK]
    lg[0][11] = "795"   # la ligne a maintenant débit ET crédit
    errs = v.valider(ecrire(tmp_path, lg))
    assert any("débit ET crédit" in e for e in errs)

def test_rejet_colonne_obligatoire_vide(tmp_path):
    lg = [row[:] for row in LIGNES_OK]
    lg[0][8] = ""   # PieceRef vide
    errs = v.valider(ecrire(tmp_path, lg))
    assert any("PieceRef" in e for e in errs)

def test_trou_numerotation_observe_mais_non_bloquant(tmp_path):
    """Un trou de numérotation est une OBSERVATION, pas un rejet.

    La notice DGFiP (question 14) admet des ruptures justifiées par la
    validation d'un brouillard : un fichier EXTERNE qui en comporte n'est
    pas pour autant non conforme. La continuité des numéros que ce logiciel
    PRODUIT, elle, reste exigée strictement — mais côté export et contrôles
    (`controles.c_numerotation_fec`), là où leur provenance est connue.
    """
    lg = [row[:] for row in LIGNES_OK]
    l3 = [["BQ","Banque","3","20260116","708810","Loyers et autres produits","","","NA","20260116","x","","10","","","20260116","",""],
          ["BQ","Banque","3","20260116","108000","Exploitant","","","NA","20260116","x","10","","","","20260116","",""]]
    rapport = v.valider(ecrire(tmp_path, lg + l3), comme_dict=True)  # le 2 manque
    assert rapport["erreurs"] == []
    assert any("non continue" in o for o in rapport["observations"])

def test_rejet_ecriture_une_seule_ligne(tmp_path):
    errs = v.valider(ecrire(tmp_path, [LIGNES_OK[0]]))  # une seule ligne
    assert any("une seule ligne" in e for e in errs)

def test_rejet_entete_incomplet(tmp_path):
    chemin = ecrire(tmp_path, LIGNES_OK, en_tete="\t".join(v.COLONNES[:17]))
    errs = v.valider(chemin)
    assert any("En-tête" in e for e in errs)

def test_rejet_mauvais_nombre_de_champs(tmp_path):
    lg = [row[:] for row in LIGNES_OK]
    lg[0] = lg[0][:17]   # 17 champs au lieu de 18
    errs = v.valider(ecrire(tmp_path, lg))
    assert any("champs au lieu de 18" in e for e in errs)


# --- Le FEC valide de base, lui, passe -------------------------------------

def test_fec_minimal_valide_passe(tmp_path):
    assert v.valider(ecrire(tmp_path, LIGNES_OK)) == []
