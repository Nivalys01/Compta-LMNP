# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

"""
Tests J2 (saisie par opérations) + moteur de contrôles + import bancaire.
Lancer :  pytest -q
"""
import os
import pytest

import init_db
import operations
import controles
import export_fec
import valider_fec
import import_bancaire as imp

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FEC2025 = os.path.join(ROOT, "reference", "FEC_REFERENCE_2025.txt")


@pytest.fixture()
def conn(tmp_path):
    c = init_db.init_demo(str(tmp_path / "t.db"), FEC2025, 2026)
    yield c
    c.close()


def lignes(conn, eid):
    return conn.execute(
        "SELECT compte_num, debit, credit FROM ligne WHERE ecriture_id=? ORDER BY id", (eid,)
    ).fetchall()


# --- J2 : saisie par gabarits ----------------------------------------------

def test_saisir_loyer_genere_ecriture_equilibree(conn):
    r = operations.saisir(conn, type="loyer", montant=795, date_operation="2026-03-05", periode="2026-03")
    lg = lignes(conn, r["ecriture_id"])
    assert (lg[0][0], lg[0][1]) == ("108000", 795.0)   # encaissement : 108000 débité
    assert (lg[1][0], lg[1][2]) == ("708810", 795.0)   # produit crédité
    assert round(sum(x[1] for x in lg), 2) == round(sum(x[2] for x in lg), 2)

def test_saisir_charge_sens_inverse(conn):
    r = operations.saisir(conn, type="charge_copro", montant=120, date_operation="2026-04-10")
    lg = lignes(conn, r["ecriture_id"])
    assert (lg[0][0], lg[0][1]) == ("614100", 120.0)   # charge débitée
    assert (lg[1][0], lg[1][2]) == ("108000", 120.0)   # 108000 crédité

def test_saisir_cree_operation_liee(conn):
    r = operations.saisir(conn, type="assurance", montant=138.49, date_operation="2026-01-15")
    op = conn.execute("SELECT type, montant, ecriture_id FROM operation WHERE id=?",
                      (r["operation_id"],)).fetchone()
    assert op == ("assurance", 138.49, r["ecriture_id"])

def test_type_inconnu_rejete(conn):
    with pytest.raises(ValueError):
        operations.saisir(conn, type="zorglub", montant=10, date_operation="2026-01-01")

def test_montant_nul_rejete(conn):
    with pytest.raises(ValueError):
        operations.saisir(conn, type="loyer", montant=0, date_operation="2026-01-01")

def test_numerotation_continue_apres_reprise(conn):
    # AN=1, OD affectation=2 ; la 1re saisie doit être n°3.
    r = operations.saisir(conn, type="loyer", montant=795, date_operation="2026-01-05", periode="2026-01")
    assert r["ecriture_num"] == 3


# --- Contrôles de cohérence -------------------------------------------------

def test_controle_doublon(conn):
    operations.saisir(conn, type="loyer", montant=795, date_operation="2026-03-05", periode="2026-03")
    operations.saisir(conn, type="loyer", montant=795, date_operation="2026-03-06", periode="2026-03")
    anos = controles.controler(conn, 2026)
    assert any(a.code == "DOUBLON" for a in anos)

def test_controle_autres_a_requalifier(conn):
    operations.saisir(conn, type="autres_charges", montant=1106, date_operation="2026-12-01",
                      libelle="Intérêts emprunt 2026")
    anos = controles.controler(conn, 2026)
    assert any(a.code == "REQUALIFIER" for a in anos)

def test_controle_depense_immobilisable(conn):
    operations.saisir(conn, type="petit_equipement", montant=1533, date_operation="2026-06-01")
    anos = controles.controler(conn, 2026)
    assert any(a.code == "IMMOBILISABLE" for a in anos)

def test_petit_equipement_sous_seuil_ok(conn):
    operations.saisir(conn, type="petit_equipement", montant=99, date_operation="2026-03-12")
    anos = controles.controler(conn, 2026)
    assert not any(a.code == "IMMOBILISABLE" for a in anos)

def test_controle_completude_loyers(conn):
    for mois in ("01", "02", "03"):   # seulement 3 mois sur 12
        operations.saisir(conn, type="loyer", montant=795, date_operation=f"2026-{mois}-05",
                          periode=f"2026-{mois}")
    anos = controles.controler(conn, 2026)
    manq = [a for a in anos if a.code == "LOYER_MANQUANT"]
    assert manq and "2026-04" in manq[0].message and "2026-12" in manq[0].message

def test_controle_equilibre_bloquant(conn):
    # Écriture manuelle déséquilibrée insérée directement.
    cur = conn.cursor()
    cur.execute("INSERT INTO ecriture (journal_code, ecriture_num, ecriture_date, exercice_annee, "
                "piece_ref, libelle, valid_date) VALUES ('OD', 99, '2026-06-01', 2026, 'X', 'bug', '2026-06-01')")
    eid = cur.lastrowid
    cur.execute("INSERT INTO ligne (ecriture_id, compte_num, debit) VALUES (?, '614100', 100)", (eid,))
    cur.execute("INSERT INTO ligne (ecriture_id, compte_num, credit) VALUES (?, '108000', 90)", (eid,))
    conn.commit()
    anos = controles.controler(conn, 2026)
    bloq = controles.bloquants(anos)
    assert any(a.code == "EQUILIBRE" for a in bloq)

def test_controle_sens_comptable(conn):
    # Charge (classe 6) au crédit, hors logique normale.
    cur = conn.cursor()
    cur.execute("INSERT INTO ecriture (journal_code, ecriture_num, ecriture_date, exercice_annee, "
                "piece_ref, libelle, valid_date) VALUES ('BQ', 98, '2026-05-01', 2026, 'X', 'x', '2026-05-01')")
    eid = cur.lastrowid
    cur.execute("INSERT INTO ligne (ecriture_id, compte_num, credit) VALUES (?, '614100', 50)", (eid,))
    cur.execute("INSERT INTO ligne (ecriture_id, compte_num, debit) VALUES (?, '108000', 50)", (eid,))
    conn.commit()
    anos = controles.controler(conn, 2026)
    assert any(a.code == "SENS" for a in anos)

def test_aucune_anomalie_si_propre(conn):
    # Le dossier de démonstration porte depuis la v8.17.0 un exercice
    # précédent COMPLET. Le sujet de ce test étant la silence des contrôles
    # sur un dossier bien tenu — et non la comparaison avec l'an dernier,
    # couverte ailleurs — on neutralise cette comparaison.
    conn.execute("DELETE FROM operation WHERE exercice_annee=2025")
    conn.commit()
    # Dossier COMPLET : 12 loyers réguliers + les charges quasi certaines
    # (taxe foncière, CFE, assurance) — aucun contrôle ne doit sortir.
    for m in range(1, 13):
        operations.saisir(conn, type="loyer", montant=795, date_operation=f"2026-{m:02d}-05",
                          periode=f"2026-{m:02d}")
    operations.saisir(conn, type="taxe_fonciere", montant=1162,
                      date_operation="2026-10-15", periode="2026-10")
    operations.saisir(conn, type="cfe", montant=341,
                      date_operation="2026-12-15", periode="2026-12")
    operations.saisir(conn, type="assurance", montant=138,
                      date_operation="2026-01-10", periode="2026-01")
    # La TEOM figure sur le MÊME avis que la taxe foncière : un dossier
    # réellement complet la porte aussi (contrôle ajouté en v8.11.0 après
    # constat d'usage — l'oubli le plus courant du dépouillement de l'avis).
    operations.saisir(conn, type="teom", montant=163,
                      date_operation="2026-10-15", periode="2026-10")
    # Les rappels de niveau INFO ne sont pas des anomalies : « aucun
    # intérêt d'emprunt » est parfaitement légitime pour un achat
    # comptant, « aucune charge de copropriété » pour une maison. Ce test
    # porte sur les VRAIES alertes — bloquantes et avertissements.
    anos = [a for a in controles.controler(conn, 2026)
            if a.niveau != controles.INFO]
    assert anos == []


# --- Import bancaire --------------------------------------------------------

@pytest.mark.parametrize("libelle,montant,attendu", [
    ("VIR LOYER MARS Locataire", 795, "loyer"),
    ("PRLV GMF ASSURANCE PNO", -138, "assurance"),
    ("PRLV SYNDIC COPRO", -200, "charge_copro"),
    ("ORANGE INTERNET", -29, "telecom"),
    ("DGFIP TAXE FONCIERE", -1162, "impot_local"),
    ("FACTURE CABINET COMPTABLE", -225, "honoraires"),
    ("ACHAT TRUC INCONNU", -42, "attente_decaissement"),  # E-06
])
def test_categoriser(libelle, montant, attendu):
    assert imp.categoriser(libelle, montant) == attendu

def test_proposer_csv(tmp_path):
    csv = tmp_path / "releve.csv"
    csv.write_text("date;libelle;montant\n05/03/2026;VIR LOYER MARS;795\n"
                   "15/01/2026;PRLV GMF PNO;-138,49\n", encoding="utf-8")
    props = imp.proposer(str(csv))
    assert len(props) == 2
    assert props[0]["type"] == "loyer" and props[0]["periode"] == "2026-03"
    assert props[1]["type"] == "assurance" and props[1]["montant"] == 138.49

def test_import_valide_insere_et_exporte_conforme(conn, tmp_path):
    csv = tmp_path / "releve.csv"
    csv.write_text("date;libelle;montant\n05/03/2026;VIR LOYER MARS;795\n"
                   "10/04/2026;PRLV SYNDIC;-120\n", encoding="utf-8")
    imp.importer(conn, str(csv), valider=True)
    sortie = export_fec.exporter(conn, 2026, str(tmp_path / "FEC2026.txt"))
    assert valider_fec.valider(sortie) == []   # le FEC reste conforme après saisie
